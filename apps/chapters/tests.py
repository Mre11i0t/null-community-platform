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

# --- Chapter sites (PRD Part 0: subdomain multi-tenancy) --------------------


def _future_event(chapter, name):
    return EventFactory(
        chapter=chapter,
        public=True,
        name=name,
        start_time=timezone.now() + datetime.timedelta(days=4),
        end_time=timezone.now() + datetime.timedelta(days=4, hours=2),
    )


def test_subdomain_autofills_from_name():
    chapter = ChapterFactory(name="New Delhi Chapter")
    assert chapter.subdomain == "new-delhi-chapter"


def test_root_host_is_not_a_chapter_site(client):
    ChapterFactory(name="Delhi")
    response = client.get("/")  # test client host is "testserver" → root
    assert response.status_code == 200
    assert response.wsgi_request.chapter is None


def test_chapter_subdomain_serves_only_that_chapters_events(client):
    delhi = ChapterFactory(name="Delhi")
    goa = ChapterFactory(name="Goa")
    ours = _future_event(delhi, "Delhi Meetup")
    theirs = _future_event(goa, "Goa Meetup")

    response = client.get("/", HTTP_HOST="delhi.localhost")

    assert response.status_code == 200
    assert response.wsgi_request.chapter == delhi
    events = list(response.context["events"])
    assert ours in events
    assert theirs not in events


def test_unknown_subdomain_404s(client):
    response = client.get("/", HTTP_HOST="atlantis.localhost")
    assert response.status_code == 404


def test_inactive_chapter_subdomain_404s(client):
    ChapterFactory(name="Ghost", active=False)
    response = client.get("/", HTTP_HOST="ghost.localhost")
    assert response.status_code == 404


def test_custom_domain_resolves_to_chapter(client):
    delhi = ChapterFactory(name="Delhi", custom_domain="NullDelhi.in")
    response = client.get("/", HTTP_HOST="nulldelhi.in")
    assert response.status_code == 200
    assert response.wsgi_request.chapter == delhi
    # save() lowercases the stored domain
    delhi.refresh_from_db()
    assert delhi.custom_domain == "nulldelhi.in"


def test_domain_check_gates_certificate_issuance(client):
    ChapterFactory(name="Delhi", custom_domain="nulldelhi.in")
    ChapterFactory(name="Ghost", active=False, custom_domain="ghost.example")

    ok = lambda d: client.get("/domains/check", {"domain": d}).status_code  # noqa: E731
    assert ok("localhost") == 200  # root domain
    assert ok("delhi.localhost") == 200  # active chapter subdomain
    assert ok("nulldelhi.in") == 200  # active custom domain
    assert ok("atlantis.localhost") == 404  # unknown subdomain
    assert ok("ghost.example") == 404  # inactive chapter
    assert ok("evil.example") == 404  # stranger's domain
    assert ok("") == 404  # missing param


def test_chapter_site_url_prefers_custom_domain():
    plain = ChapterFactory(name="Goa")
    custom = ChapterFactory(name="Delhi", custom_domain="nulldelhi.in")
    assert plain.site_url() == "http://goa.localhost:8000"
    assert custom.site_url() == "http://nulldelhi.in:8000"
