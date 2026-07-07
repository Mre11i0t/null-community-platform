import json

import pytest
from django.urls import reverse

from apps.events.models import Event, EventRegistration, EventSession, Venue
from apps.notifications.models import EventMailerTask
from tests.factories import (
    ChapterFactory,
    ChapterLeadFactory,
    EventFactory,
    EventRegistrationFactory,
    EventSessionFactory,
    EventTypeFactory,
    UserFactory,
    VenueFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def lead_and_chapter():
    chapter = ChapterFactory()
    lead = ChapterLeadFactory(chapter=chapter).user
    return lead, chapter


# --- Permission boundary: require_leader / managed_chapter ------------------


def test_leads_pages_require_login(client):
    response = client.get(reverse("leads:event_index"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_leads_pages_forbidden_for_non_leader(client):
    client.force_login(UserFactory())
    response = client.get(reverse("leads:event_index"))
    assert response.status_code == 403


def test_event_show_forbidden_for_leader_of_a_different_chapter(client, lead_and_chapter):
    lead, _my_chapter = lead_and_chapter
    other_chapter = ChapterFactory()
    other_event = EventFactory(chapter=other_chapter)

    client.force_login(lead)
    response = client.get(reverse("leads:event_show", args=[other_event.pk]))

    assert response.status_code == 403


def test_event_show_allowed_for_own_chapter(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)

    client.force_login(lead)
    response = client.get(reverse("leads:event_show", args=[event.pk]))

    assert response.status_code == 200


# --- Events ------------------------------------------------------------------


def test_event_new_forces_not_public(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    venue = VenueFactory(chapter=chapter)
    event_type = EventTypeFactory()
    client.force_login(lead)

    response = client.post(
        reverse("leads:event_new"),
        {
            "event_type": event_type.pk,
            "chapter": chapter.pk,
            "name": "New Meetup",
            "venue": venue.pk,
            "description": "desc",
            "start_time": "2027-01-01T18:00",
            "end_time": "2027-01-01T20:00",
            "max_registration": 0,
        },
    )

    assert response.status_code == 302
    event = Event.objects.get(name="New Meetup")
    assert event.public is False


def test_event_new_chapter_choices_scoped_to_managed_chapters(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    ChapterFactory()  # a chapter this lead does not manage

    client.force_login(lead)
    response = client.get(reverse("leads:event_new"))

    assert list(response.context["form"].fields["chapter"].queryset) == [chapter]


def test_event_delete_is_disabled(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    client.force_login(lead)

    client.post(reverse("leads:event_delete", args=[event.pk]))

    assert Event.objects.filter(pk=event.pk).exists()


# --- Event Sessions ------------------------------------------------------


def test_session_new_and_show(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    speaker = UserFactory()
    client.force_login(lead)

    response = client.post(
        reverse("leads:session_new", args=[event.pk]),
        {
            "user": speaker.pk,
            "name": "A Talk",
            "description": "desc",
            "start_time": "2027-01-01T18:00",
            "end_time": "2027-01-01T18:30",
        },
    )

    assert response.status_code == 302
    session = EventSession.objects.get(name="A Talk", event=event)
    assert session.user == speaker


def test_session_delete_is_disabled(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    session = EventSessionFactory(event=event)
    client.force_login(lead)

    client.post(reverse("leads:session_delete", args=[event.pk, session.pk]))

    assert EventSession.objects.filter(pk=session.pk).exists()


def test_session_suggest_user_searches_by_name_or_email(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    match = UserFactory(name="Jane Speaker", email="jane@example.com")
    UserFactory(name="No Match", email="nomatch@example.com")
    client.force_login(lead)

    response = client.get(reverse("leads:session_suggest_user", args=[event.pk]), {"q": "jane"})

    assert response.status_code == 200
    payload = json.loads(response.content)
    assert [row["id"] for row in payload] == [match.pk]


# --- Venues --------------------------------------------------------------


def test_venue_new_rejects_a_chapter_the_user_does_not_manage(client, lead_and_chapter):
    lead, _chapter = lead_and_chapter
    other_chapter = ChapterFactory()
    client.force_login(lead)

    response = client.post(
        reverse("leads:venue_new"),
        {
            "chapter": other_chapter.pk,
            "name": "Sneaky Venue",
            "address": "somewhere",
            "contact_name": "x",
        },
    )

    # form's chapter queryset is scoped to managed_chapters(), so this chapter_id
    # isn't a valid choice and the form should reject it rather than save.
    assert not Venue.objects.filter(name="Sneaky Venue").exists()
    assert response.status_code == 200
    assert "chapter" in response.context["form"].errors


def test_venue_new_success(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    client.force_login(lead)

    response = client.post(
        reverse("leads:venue_new"),
        {"chapter": chapter.pk, "name": "New Venue", "address": "somewhere", "contact_name": "x"},
    )

    assert response.status_code == 302
    assert Venue.objects.filter(name="New Venue", chapter=chapter).exists()


def test_venue_show_forbidden_for_a_venue_in_another_chapter(client, lead_and_chapter):
    lead, _chapter = lead_and_chapter
    other_venue = VenueFactory()
    client.force_login(lead)

    response = client.get(reverse("leads:venue_show", args=[other_venue.pk]))

    assert response.status_code == 403


def test_venue_delete_is_disabled(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    venue = VenueFactory(chapter=chapter)
    client.force_login(lead)

    client.post(reverse("leads:venue_delete", args=[venue.pk]))

    assert Venue.objects.filter(pk=venue.pk).exists()


# --- Event Registrations --------------------------------------------------


def test_registration_export_csv_contains_registration_rows(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    registration = EventRegistrationFactory(event=event)
    client.force_login(lead)

    response = client.get(reverse("leads:registration_export_csv", args=[event.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    body = response.content.decode()
    assert registration.user.email in body


def test_registration_mass_update_applies_valid_states_and_reports_errors(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    registration = EventRegistrationFactory(event=event)

    client.force_login(lead)
    response = client.post(
        reverse("leads:registration_mass_update", args=[event.pk]),
        data=json.dumps(
            {
                "event_registrations": [
                    {"id": registration.pk, "state": EventRegistration.STATE_ABSENT},
                    {"id": 999999, "state": EventRegistration.STATE_ABSENT},
                ]
            }
        ),
        content_type="application/json",
    )

    payload = json.loads(response.content)
    assert payload["status"] == "FAILED"
    assert len(payload["errors"]) == 1
    registration.refresh_from_db()
    assert registration.state == EventRegistration.STATE_ABSENT


def test_registration_mass_update_rejects_invalid_state(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    registration = EventRegistrationFactory(event=event)

    client.force_login(lead)
    response = client.post(
        reverse("leads:registration_mass_update", args=[event.pk]),
        data=json.dumps({"event_registrations": [{"id": registration.pk, "state": "Not A Real State"}]}),
        content_type="application/json",
    )

    payload = json.loads(response.content)
    assert payload["status"] == "FAILED"
    registration.refresh_from_db()
    assert registration.state != "Not A Real State"


# --- Event Mailer Tasks ----------------------------------------------------


def test_mailer_task_execute_forbidden_for_a_different_chapters_event(client, lead_and_chapter):
    lead, _chapter = lead_and_chapter
    other_event = EventFactory()
    task = EventMailerTask.objects.create(event=other_event, subject="s", body="b")
    client.force_login(lead)

    response = client.post(reverse("leads:mailer_task_execute", args=[other_event.pk, task.pk]))

    assert response.status_code == 403
    task.refresh_from_db()
    assert task.executed is False


def test_mailer_task_execute_success_sends_the_email(client, lead_and_chapter):
    from django.core import mail

    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    EventRegistrationFactory(event=event)
    task = EventMailerTask.objects.create(event=event, subject="s", body="b")
    client.force_login(lead)
    mail.outbox.clear()

    response = client.post(reverse("leads:mailer_task_execute", args=[event.pk, task.pk]))

    assert response.status_code == 302
    task.refresh_from_db()
    assert task.executed is True
    assert task.ready_for_delivery is False
    assert len(mail.outbox) == 1


# --- Chapters --------------------------------------------------------------


def test_chapter_index_only_lists_managed_chapters(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    ChapterFactory()

    client.force_login(lead)
    response = client.get(reverse("leads:chapter_index"))

    assert list(response.context["chapters"]) == [chapter]


def test_chapter_edit_forbidden_for_unmanaged_chapter(client, lead_and_chapter):
    lead, _chapter = lead_and_chapter
    other_chapter = ChapterFactory()
    client.force_login(lead)

    response = client.get(reverse("leads:chapter_edit", args=[other_chapter.pk]))

    assert response.status_code == 403


def test_chapter_edit_updates_the_chapter(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    client.force_login(lead)

    response = client.post(
        reverse("leads:chapter_edit", args=[chapter.pk]),
        {
            "chapter_email": "new@example.com",
            "description": "Updated description",
            "city": "Pune",
            "state": "MH",
            "country": "IN",
        },
    )

    assert response.status_code == 302
    chapter.refresh_from_db()
    assert chapter.chapter_email == "new@example.com"


# --- Remaining index/show/edit views (coverage completeness pass) ----------


def test_event_index_switches_between_current_and_old_events(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    client.force_login(lead)

    response = client.get(reverse("leads:event_index"))
    assert response.status_code == 200
    assert response.context["show_old"] is None

    response = client.get(reverse("leads:event_index"), {"show_old": "1"})
    assert response.status_code == 200
    assert response.context["show_old"] == "1"


def test_event_edit_updates_the_event(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter, name="Old Name")
    client.force_login(lead)

    response = client.post(
        reverse("leads:event_edit", args=[event.pk]),
        {
            "event_type": event.event_type.pk,
            "chapter": chapter.pk,
            "name": "New Name",
            "venue": event.venue.pk,
            "description": "desc",
            "start_time": "2027-01-01T18:00",
            "end_time": "2027-01-01T20:00",
            "max_registration": 0,
        },
    )

    assert response.status_code == 302
    event.refresh_from_db()
    assert event.name == "New Name"


def test_event_edit_forbidden_for_a_different_chapter(client, lead_and_chapter):
    lead, _chapter = lead_and_chapter
    other_event = EventFactory()
    client.force_login(lead)

    response = client.get(reverse("leads:event_edit", args=[other_event.pk]))

    assert response.status_code == 403


def test_session_index_and_show(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    session = EventSessionFactory(event=event)
    client.force_login(lead)

    response = client.get(reverse("leads:session_index", args=[event.pk]))
    assert response.status_code == 200
    assert session in response.context["sessions"]

    response = client.get(reverse("leads:session_show", args=[event.pk, session.pk]))
    assert response.status_code == 200
    assert response.context["session"] == session


def test_session_edit_updates_the_session(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    session = EventSessionFactory(event=event, name="Old Title")
    client.force_login(lead)

    response = client.post(
        reverse("leads:session_edit", args=[event.pk, session.pk]),
        {
            "user": session.user.pk,
            "name": "New Title",
            "description": "desc",
            "start_time": "2027-01-01T18:00",
            "end_time": "2027-01-01T18:30",
        },
    )

    assert response.status_code == 302
    session.refresh_from_db()
    assert session.name == "New Title"


def test_venue_index_only_shows_managed_venues(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    mine = VenueFactory(chapter=chapter)
    VenueFactory()  # someone else's
    client.force_login(lead)

    response = client.get(reverse("leads:venue_index"))

    assert list(response.context["venues"]) == [mine]


def test_venue_edit_updates_the_venue(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    venue = VenueFactory(chapter=chapter, name="Old Venue Name")
    client.force_login(lead)

    response = client.post(
        reverse("leads:venue_edit", args=[venue.pk]),
        {
            "chapter": chapter.pk,
            "name": "New Venue Name",
            "address": "123 St",
            "contact_name": "x",
        },
    )

    assert response.status_code == 302
    venue.refresh_from_db()
    assert venue.name == "New Venue Name"


def test_registration_index_shows_registrations(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    registration = EventRegistrationFactory(event=event)
    client.force_login(lead)

    response = client.get(reverse("leads:registration_index", args=[event.pk]))

    assert response.status_code == 200
    assert registration in response.context["registrations"]


def test_mailer_task_index_show_new_edit(client, lead_and_chapter):
    lead, chapter = lead_and_chapter
    event = EventFactory(chapter=chapter)
    client.force_login(lead)

    response = client.post(
        reverse("leads:mailer_task_new", args=[event.pk]),
        {"subject": "Hello", "body": "World", "registration_state": ""},
    )
    assert response.status_code == 302
    task = EventMailerTask.objects.get(event=event, subject="Hello")

    response = client.get(reverse("leads:mailer_task_index", args=[event.pk]))
    assert response.status_code == 200
    assert task in response.context["tasks"]

    response = client.get(reverse("leads:mailer_task_show", args=[event.pk, task.pk]))
    assert response.status_code == 200
    assert response.context["task"] == task

    response = client.post(
        reverse("leads:mailer_task_edit", args=[event.pk, task.pk]),
        {"subject": "Updated", "body": "World", "registration_state": "", "ready_for_delivery": "on"},
    )
    assert response.status_code == 302
    task.refresh_from_db()
    assert task.subject == "Updated"
    # editing forces ready_for_delivery back to False regardless of what was posted,
    # to prevent an edit accidentally re-triggering delivery.
    assert task.ready_for_delivery is False


def test_lead_publish_toggle_fires_published_webhook(client, monkeypatch):
    import datetime as dt

    from django.utils import timezone as tz

    from apps.notifications.models import WebhookEndpoint
    from tests.factories import ChapterLeadFactory, EventFactory

    calls = []
    import requests

    class FakeResponse:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        requests, "post", lambda *a, **kw: calls.append(kw.get("headers", {})) or FakeResponse()
    )

    event = EventFactory(
        public=False,
        start_time=tz.now() + dt.timedelta(days=5),
        end_time=tz.now() + dt.timedelta(days=5, hours=2),
    )
    WebhookEndpoint.objects.create(chapter=event.chapter, url="https://example.com/hook")
    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)

    client.post(reverse("leads:event_publish", args=[event.pk]))
    event.refresh_from_db()
    assert event.public is True
    assert any(h.get("X-Null-Event") == "event.published" for h in calls)

    client.post(reverse("leads:event_publish", args=[event.pk]))
    event.refresh_from_db()
    assert event.public is False
