import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User
from tests.factories import EventRegistrationFactory, EventSessionFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_user_factory_creates_usable_password():
    user = UserFactory(password="mypassword123")
    assert user.check_password("mypassword123")


def test_signup_creates_user_and_sends_confirmation_email(client):
    response = client.post(
        reverse("account_signup"),
        {
            "email": "newmember@example.com",
            "password1": "a-strong-password-1",
            "password2": "a-strong-password-1",
            "g-recaptcha-response": "PASSED",
        },
    )
    assert response.status_code == 302
    assert User.objects.filter(email="newmember@example.com").exists()
    assert len(mail.outbox) == 1
    assert "newmember@example.com" in mail.outbox[0].to[0]


def test_public_profile_shows_speaker_sessions_and_registrations(client):
    user = UserFactory()
    session = EventSessionFactory(user=user)
    registration = EventRegistrationFactory(user=user)
    registration.state = registration.STATE_CONFIRMED
    registration.save()

    response = client.get(reverse("accounts:public_profile", args=[user.pk]))

    assert response.status_code == 200
    assert session in response.context["speaker_sessions"]
    assert registration in response.context["registered_participation"]
