import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import UserApiToken
from tests.factories import (
    ChapterFactory,
    EventFactory,
    EventRegistrationFactory,
    EventSessionFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --- Public resource endpoints ------------------------------------------------


def test_chapters_default_only_active(client):
    active = ChapterFactory(active=True)
    ChapterFactory(active=False)

    response = client.get(reverse("api:chapters"))

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()["results"]] if "results" in response.json() else [
        row["id"] for row in response.json()
    ]
    assert active.pk in ids


def test_chapters_all_true_includes_inactive(client):
    active = ChapterFactory(active=True)
    inactive = ChapterFactory(active=False)

    response = client.get(reverse("api:chapters"), {"all": "true"})

    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert active.pk in ids
    assert inactive.pk in ids


def test_events_default_only_future_public(client):
    future_public = EventFactory(
        public=True,
        start_time=timezone.now() + datetime.timedelta(days=1),
        end_time=timezone.now() + datetime.timedelta(days=1, hours=2),
    )
    EventFactory(public=False)

    response = client.get(reverse("api:events"))

    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert future_public.pk in ids


def test_event_sessions_scoped_to_a_public_event(client):
    event = EventFactory(public=True)
    session = EventSessionFactory(event=event)
    private_event = EventFactory(public=False)
    EventSessionFactory(event=private_event)

    response = client.get(reverse("api:event_sessions", args=[event.pk]))
    assert response.status_code == 200
    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert ids == [session.pk]

    response = client.get(reverse("api:event_sessions", args=[private_event.pk]))
    assert response.json().get("results", response.json()) == []


def test_event_registrations_only_visible(client):
    event = EventFactory(public=True)
    visible = EventRegistrationFactory(event=event, visible=True)
    EventRegistrationFactory(event=event, visible=False)

    response = client.get(reverse("api:event_registrations", args=[event.pk]))

    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert ids == [visible.pk]


# --- Password authentication --------------------------------------------------


def test_authenticate_password_success_issues_token(client):
    user = UserFactory(password="correct-password")

    response = client.post(
        reverse("api:authenticate_password"),
        {"email": user.email, "password": "correct-password", "client_name": "test-client"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert UserApiToken.objects.filter(token=body["token"], user=user, active=True).exists()


def test_authenticate_password_wrong_password_is_401(client):
    user = UserFactory(password="correct-password")

    response = client.post(
        reverse("api:authenticate_password"),
        {"email": user.email, "password": "wrong-password", "client_name": "test-client"},
    )

    assert response.status_code == 401


def test_authenticate_password_missing_fields_is_400(client):
    response = client.post(reverse("api:authenticate_password"), {"email": "x@example.com"})
    assert response.status_code == 400


# --- Bearer token auth on protected endpoints --------------------------------


def _issue_token(user):
    return UserApiToken.objects.create(
        user=user, client_name="test", active=True, expire_at=timezone.now() + datetime.timedelta(days=1)
    )


def test_users_me_requires_a_token(client):
    response = client.get(reverse("api:user_me"))
    assert response.status_code == 401


def test_users_me_rejects_an_expired_token(client):
    user = UserFactory()
    token = UserApiToken.objects.create(
        user=user, client_name="test", active=True, expire_at=timezone.now() - datetime.timedelta(hours=1)
    )

    response = client.get(reverse("api:user_me"), HTTP_AUTHORIZATION=f"Bearer {token.token}")

    assert response.status_code == 401


def test_users_me_rejects_an_inactive_token(client):
    user = UserFactory()
    token = UserApiToken.objects.create(
        user=user,
        client_name="test",
        active=False,
        expire_at=timezone.now() + datetime.timedelta(days=1),
    )

    response = client.get(reverse("api:user_me"), HTTP_AUTHORIZATION=f"Bearer {token.token}")

    assert response.status_code == 401


def test_users_me_with_valid_token(client):
    user = UserFactory(email="tokentest@example.com")
    token = _issue_token(user)

    response = client.get(reverse("api:user_me"), HTTP_AUTHORIZATION=f"Bearer {token.token}")

    assert response.status_code == 200
    assert response.json()["email"] == "tokentest@example.com"


def test_users_events_scoped_to_the_authenticated_user(client):
    user = UserFactory()
    token = _issue_token(user)
    my_registration = EventRegistrationFactory(user=user)
    my_registration.accepted = True
    my_registration.save()
    EventRegistrationFactory()  # someone else's

    response = client.get(reverse("api:user_events"), HTTP_AUTHORIZATION=f"Bearer {token.token}")

    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert ids == [my_registration.event_id]


def test_users_sessions_scoped_to_the_authenticated_user(client):
    user = UserFactory()
    token = _issue_token(user)
    my_session = EventSessionFactory(user=user, placeholder=False)
    EventSessionFactory(placeholder=False)  # someone else's

    response = client.get(reverse("api:user_sessions"), HTTP_AUTHORIZATION=f"Bearer {token.token}")

    body = response.json()
    ids = [row["id"] for row in body.get("results", body)]
    assert ids == [my_session.pk]
