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


def test_login_by_email_succeeds_with_correct_password(client):
    """ACCOUNT_AUTHENTICATION_METHOD="email" / ACCOUNT_USERNAME_REQUIRED=False
    are this project's own settings, not allauth defaults — worth a real
    (non-force_login) pass through the login view rather than just trusting
    the config."""
    UserFactory(email="logintest@example.com", password="correct-password")

    response = client.post(
        reverse("account_login"),
        {"login": "logintest@example.com", "password": "correct-password"},
    )

    assert response.status_code == 302
    response = client.get(reverse("core:home"))
    assert response.wsgi_request.user.is_authenticated


def test_login_by_email_fails_with_wrong_password(client):
    UserFactory(email="logintest2@example.com", password="correct-password")

    response = client.post(
        reverse("account_login"),
        {"login": "logintest2@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 200  # re-renders the form, doesn't redirect
    response = client.get(reverse("core:home"))
    assert not response.wsgi_request.user.is_authenticated


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
