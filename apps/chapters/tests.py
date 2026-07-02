import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from tests.factories import ChapterFactory, EventFactory

pytestmark = pytest.mark.django_db


def test_list_shows_all_chapters(client):
    active = ChapterFactory(active=True)
    inactive = ChapterFactory(active=False)

    response = client.get(reverse("chapters:list"))

    assert response.status_code == 200
    names = {c.name for c in response.context["chapters"]}
    assert active.name in names
    assert inactive.name in names


def test_detail_splits_upcoming_and_past_events(client):
    chapter = ChapterFactory()
    upcoming = EventFactory(
        chapter=chapter,
        public=True,
        start_time=timezone.now() + datetime.timedelta(days=5),
        end_time=timezone.now() + datetime.timedelta(days=5, hours=2),
    )
    past = EventFactory(
        chapter=chapter,
        public=True,
        can_show_on_archive=True,
        start_time=timezone.now() - datetime.timedelta(days=5),
        end_time=timezone.now() - datetime.timedelta(days=5, hours=-2),
    )

    response = client.get(reverse("chapters:detail", args=[chapter.pk]))

    assert response.status_code == 200
    assert upcoming in response.context["upcoming_events"]
    assert past in response.context["past_events"]
    assert upcoming not in response.context["past_events"]
    assert past not in response.context["upcoming_events"]


def test_detail_404s_for_unknown_chapter(client):
    response = client.get(reverse("chapters:detail", args=[999999]))
    assert response.status_code == 404


def test_calendar_ics_contains_upcoming_event_as_a_vevent(client):
    chapter = ChapterFactory(name="ICS Test Chapter")
    event = EventFactory(
        chapter=chapter,
        public=True,
        name="ICS Event",
        start_time=timezone.now() + datetime.timedelta(days=3),
        end_time=timezone.now() + datetime.timedelta(days=3, hours=2),
    )

    response = client.get(reverse("chapters:calendar_ics", args=[chapter.pk]))

    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar"
    body = response.content.decode()
    assert "BEGIN:VCALENDAR" in body
    assert "BEGIN:VEVENT" in body
    assert f"swachalit-event-{event.pk}" in body
    assert "ICS Event" in body


def test_calendar_ics_excludes_non_public_events(client):
    chapter = ChapterFactory()
    EventFactory(chapter=chapter, public=False, name="Private Event")

    response = client.get(reverse("chapters:calendar_ics", args=[chapter.pk]))

    assert "Private Event" not in response.content.decode()
