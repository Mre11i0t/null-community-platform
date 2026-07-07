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
            "coc_accept": "on",
        },
    )
    assert response.status_code == 302
    user = User.objects.get(email="newmember@example.com")
    assert user.has_acknowledged_coc()  # Rev 3: recorded at signup
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


# --- Rev 3 trust & safety ------------------------------------------------------


def test_signup_rejected_without_coc_acceptance(client):
    response = client.post(
        reverse("account_signup"),
        {
            "email": "refusenik@example.com",
            "password1": "a-strong-password-1",
            "password2": "a-strong-password-1",
            "g-recaptcha-response": "PASSED",
        },
    )
    assert response.status_code == 200  # re-renders with error
    assert not User.objects.filter(email="refusenik@example.com").exists()


def test_rsvp_reprompts_coc_after_version_bump(client, settings):
    import datetime

    from django.utils import timezone

    from tests.factories import EventFactory

    user = UserFactory()  # acked v1.0 via factory
    settings.COC_VERSION = "2.0"  # policy bumped
    event = EventFactory(
        registration_start_time=timezone.now() - datetime.timedelta(days=1),
        registration_end_time=timezone.now() + datetime.timedelta(days=1),
        start_time=timezone.now() + datetime.timedelta(days=2),
        end_time=timezone.now() + datetime.timedelta(days=2, hours=2),
    )
    client.force_login(user)
    url = reverse("events:registration_new", args=[event.pk])

    # without accepting the new version, RSVP fails
    response = client.post(url, {"visible": "on", "g-recaptcha-response": "PASSED"})
    assert response.status_code == 200
    assert not event.event_registrations.filter(user=user).exists()

    # accepting records v2.0
    response = client.post(
        url, {"visible": "on", "g-recaptcha-response": "PASSED", "coc_accept": "on"}
    )
    assert response.status_code == 302
    assert user.coc_acknowledgements.filter(version="2.0").exists()


def test_incident_report_creates_record_and_emails_team(client, settings):
    from django.core import mail

    from apps.core.models import IncidentReport

    settings.INCIDENT_RESPONSE_ADDRESSES = ["conduct@null.community"]
    user = UserFactory()
    client.force_login(user)
    mail.outbox.clear()

    response = client.post(
        reverse("accounts:report_incident"),
        {"description": "Something happened", "where": "Delhi meetup", "contact_ok": "on"},
    )

    assert response.status_code == 200
    report = IncidentReport.objects.get()
    assert report.reporter == user and report.state == IncidentReport.STATE_OPEN
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["conduct@null.community"]
    assert "CONFIDENTIAL" in mail.outbox[0].subject


def test_account_deletion_anonymizes_but_keeps_history(client):
    from tests.factories import EventRegistrationFactory

    user = UserFactory(password="hunter2hunter2")
    registration = EventRegistrationFactory(user=user)
    client.force_login(user)

    # wrong password refuses
    client.post(reverse("accounts:delete_account"), {"password": "wrong"})
    user.refresh_from_db()
    assert user.is_active

    client.post(reverse("accounts:delete_account"), {"password": "hunter2hunter2"})
    user.refresh_from_db()
    assert not user.is_active
    assert user.email == f"deleted-{user.pk}@anonymized.invalid"
    assert user.name == "Deleted Member"
    assert registration in user.event_registrations.all()  # history retained


def test_data_export_contains_registrations_and_profile(client):
    from tests.factories import EventRegistrationFactory

    user = UserFactory()
    EventRegistrationFactory(user=user)
    client.force_login(user)

    response = client.get(reverse("accounts:export_data"))

    assert response.status_code == 200
    data = response.json()
    assert data["profile"]["email"] == user.email
    assert len(data["registrations"]) == 1
    assert data["coc_acknowledgements"]


def test_2fa_required_for_leads_when_enforced(client, settings):
    from tests.factories import ChapterLeadFactory

    settings.REQUIRE_2FA_FOR_PRIVILEGED = True
    lead = ChapterLeadFactory()
    client.force_login(lead.user)

    response = client.get(reverse("leads:event_index"))
    assert response.status_code == 302
    assert "/accounts/2fa/totp/activate" in response.url

    # ordinary member pages unaffected
    assert client.get(reverse("core:home")).status_code == 200
