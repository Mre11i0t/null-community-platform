import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.chapters.models import Chapter
from tests.factories import (
    ChapterFactory,
    EventFactory,
    EventSessionFactory,
    EventTypeFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --- Home / upcoming / archives ----------------------------------------------


def test_chapter_home_shows_future_public_events(client):
    """Rev 3: the event homepage lives on the chapter site; the root
    host serves the directory instead (tested below)."""
    chapter = ChapterFactory(active=True, name="Hometest")
    ChapterFactory(active=False)
    future = EventFactory(
        chapter=chapter,
        public=True,
        start_time=timezone.now() + datetime.timedelta(days=1),
        end_time=timezone.now() + datetime.timedelta(days=1, hours=1),
    )
    past = EventFactory(
        chapter=chapter,
        public=True,
        start_time=timezone.now() - datetime.timedelta(days=1),
        end_time=timezone.now() - datetime.timedelta(hours=22),
    )

    response = client.get("/", HTTP_HOST="hometest.localhost")

    assert response.status_code == 200
    assert future in response.context["events"]
    assert past not in response.context["events"]


def test_root_home_is_the_chapter_directory(client):
    active = ChapterFactory(active=True)
    ChapterFactory(active=False)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert active in response.context["chapters"]
    assert response.context["totals"]["chapters"] == 1
    assert "events" not in response.context  # no aggregated event listing


def test_start_chapter_application_emails_admins(client):
    from django.core import mail

    mail.outbox.clear()
    response = client.post(
        reverse("core:start_chapter"),
        {"name": "Asha", "email": "asha@example.com", "city": "Kochi", "motivation": "Local scene!"},
    )
    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert "Kochi" in mail.outbox[0].subject
    assert "asha@example.com" in mail.outbox[0].body


def test_global_session_search_filters_by_text(client):
    from tests.factories import EventSessionFactory

    hit = EventSessionFactory(name="Advanced Android Forensics")
    miss = EventSessionFactory(name="Intro to Networking")
    hit.event.public = True; hit.event.save()
    miss.event.public = True; miss.event.save()

    response = client.get(reverse("core:session_search"), {"q": "android"})
    names = [s.name for s in response.context["page_obj"].object_list]
    assert "Advanced Android Forensics" in names
    assert "Intro to Networking" not in names


def test_archives_paginates_past_events(client):
    for _ in range(30):
        EventFactory(
            public=True,
            can_show_on_archive=True,
            start_time=timezone.now() - datetime.timedelta(days=10),
            end_time=timezone.now() - datetime.timedelta(days=10, hours=-2),
        )

    response = client.get(reverse("core:archives"))

    assert response.status_code == 200
    assert response.context["page_obj"].paginator.count == 30
    assert len(response.context["page_obj"].object_list) == 25


# --- Static / embed pages ---------------------------------------------------


@pytest.mark.parametrize("url_name", ["core:about", "core:privacy", "core:calendar"])
def test_static_embed_pages_render(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 200


# --- Stats ---------------------------------------------------------------


def test_stats_index_redirects_to_last_year(client):
    response = client.get(reverse("core:stats_index"))
    assert response.status_code == 302
    assert str(timezone.now().year - 1) in response.url


def test_stats_show_computes_real_counts_for_the_year(client):
    chapter = ChapterFactory()
    event_type = EventTypeFactory()
    speaker = UserFactory(name="Prolific Speaker")

    this_year_event = EventFactory(
        chapter=chapter,
        event_type=event_type,
        public=True,
        start_time=timezone.datetime(2026, 3, 1, tzinfo=timezone.get_current_timezone()),
        end_time=timezone.datetime(2026, 3, 1, 2, tzinfo=timezone.get_current_timezone()),
    )
    EventSessionFactory(event=this_year_event, user=speaker, placeholder=False)
    EventSessionFactory(event=this_year_event, user=speaker, placeholder=False)
    # A different year — must not be counted.
    other_year_event = EventFactory(
        chapter=chapter,
        public=True,
        start_time=timezone.datetime(2025, 3, 1, tzinfo=timezone.get_current_timezone()),
        end_time=timezone.datetime(2025, 3, 1, 2, tzinfo=timezone.get_current_timezone()),
    )
    EventSessionFactory(event=other_year_event, placeholder=False)

    response = client.get(reverse("core:stats_show", args=[2026]))

    assert response.status_code == 200
    assert response.context["stat"].events().count() == 1
    assert response.context["stat"].event_sessions().count() == 2
    top_speakers = response.context["top_speakers"]
    assert top_speakers[0][0] == speaker
    assert top_speakers[0][1] == 2


def test_stats_show_filters_by_chapter(client):
    chapter_a = ChapterFactory()
    chapter_b = ChapterFactory()
    year = timezone.datetime(2026, 5, 1, tzinfo=timezone.get_current_timezone())
    EventFactory(chapter=chapter_a, public=True, start_time=year, end_time=year + datetime.timedelta(hours=2))
    EventFactory(chapter=chapter_b, public=True, start_time=year, end_time=year + datetime.timedelta(hours=2))

    response = client.get(reverse("core:stats_show", args=[2026]), {"chapter_id": chapter_a.pk})

    assert response.context["chapter"] == chapter_a
    assert response.context["stat"].events().count() == 1


# --- Rev 3 SEO ---------------------------------------------------------------


def test_sitemap_scopes_to_chapter_host(client):
    from tests.factories import ChapterFactory, EventFactory

    delhi = ChapterFactory(name="Delhi")
    goa = ChapterFactory(name="Goa")
    future = timezone.now() + datetime.timedelta(days=3)
    ours = EventFactory(chapter=delhi, public=True, start_time=future, end_time=future + datetime.timedelta(hours=2))
    theirs = EventFactory(chapter=goa, public=True, start_time=future, end_time=future + datetime.timedelta(hours=2))

    body = client.get("/sitemap.xml", HTTP_HOST="delhi.localhost").content.decode()
    assert f"/events/{ours.pk}/" in body
    assert f"/events/{theirs.pk}/" not in body
    assert "delhi.localhost" in body

    root_body = client.get("/sitemap.xml").content.decode()
    assert f"/events/{ours.pk}/" in root_body and f"/events/{theirs.pk}/" in root_body


def test_robots_txt_points_to_host_sitemap(client):
    body = client.get("/robots.txt").content.decode()
    assert "Sitemap: http://testserver/sitemap.xml" in body
    assert "Disallow: /admin/" in body


def test_event_page_has_json_ld_and_canonical(client):
    from tests.factories import EventFactory

    future = timezone.now() + datetime.timedelta(days=3)
    event = EventFactory(public=True, start_time=future, end_time=future + datetime.timedelta(hours=2))

    body = client.get(reverse("events:detail", args=[event.pk])).content.decode()
    assert '"@type": "Event"' in body
    assert 'rel="canonical"' in body
    assert event.chapter.site_url() in body
    assert 'property="og:title"' in body


# --- Rails-parity closures (Rev 3) --------------------------------------------


def test_chapter_json_endpoints(client):
    from tests.factories import ChapterLeadFactory

    lead = ChapterLeadFactory()
    chapter = lead.chapter
    future = timezone.now() + datetime.timedelta(days=4)
    event = EventFactory(chapter=chapter, public=True, start_time=future, end_time=future + datetime.timedelta(hours=2))

    leaders = client.get(f"/chapters/{chapter.pk}/leaders").json()
    assert any(row["id"] == lead.user.pk for row in leaders)

    events = client.get(f"/chapters/{chapter.pk}/upcoming_events").json()
    assert events[0]["id"] == event.pk
    assert chapter.subdomain in events[0]["url"]


def test_event_name_alias_redirects_to_canonical(client):
    future = timezone.now() + datetime.timedelta(days=4)
    event = EventFactory(name="Monthly Meetup July", public=True, start_time=future, end_time=future + datetime.timedelta(hours=2))
    assert event.slug == "monthly-meetup-july"

    response = client.get(f"/event/{event.slug}")
    assert response.status_code == 302
    assert response.url == f"/events/{event.pk}/"

    assert client.get("/event/nonexistent-thing").status_code == 404


def test_session_archive_filters(client):
    from tests.factories import EventSessionFactory

    with_slides = EventSessionFactory(name="Talk With Slides", presentation_url="https://slides.example.com/x")
    without = EventSessionFactory(name="Talk Without Anything")
    for session in (with_slides, without):
        session.event.public = True
        session.event.save()
    with_slides.tags.add("redteam")

    names = [s.name for s in client.get("/sessions/", {"has_reference": "1"}).context["page_obj"].object_list]
    assert "Talk With Slides" in names and "Talk Without Anything" not in names

    names = [s.name for s in client.get("/sessions/", {"tag": "redteam"}).context["page_obj"].object_list]
    assert names == ["Talk With Slides"]

    # legacy Rails path serves the same view
    assert client.get("/event_sessions").status_code == 200


def test_page_access_permissions_enforced(client):
    from apps.content.models import Page, PageAccessPermission

    page = Page.objects.create(
        name="CoC", description="d", navigation_name="CoC", title="Code of Conduct",
        content="<p>be nice</p>", published=True,
    )
    edit_url = f"/pages/{page.slug}/edit/"

    nobody = UserFactory()
    client.force_login(nobody)
    assert client.get(edit_url).status_code == 404

    reader = UserFactory()
    PageAccessPermission.objects.create(page=page, user=reader, permission_type=PageAccessPermission.READ_ONLY)
    client.force_login(reader)
    response = client.get(edit_url)
    assert response.status_code == 200 and not response.context["can_write"]
    client.post(edit_url, {"title": "Hacked", "content": "x"})
    page.refresh_from_db()
    assert page.title == "Code of Conduct"  # read-only can't write

    writer = UserFactory()
    PageAccessPermission.objects.create(page=page, user=writer, permission_type=PageAccessPermission.READ_WRITE)
    client.force_login(writer)
    client.post(edit_url, {"title": "Code of Conduct v2", "content": "<p>be nicer</p>"})
    page.refresh_from_db()
    assert page.title == "Code of Conduct v2"


def test_password_change_invalidates_api_tokens(client):
    from allauth.account.signals import password_changed

    from apps.accounts.models import UserApiToken

    user = UserFactory(password="oldpass-123456")
    token = UserApiToken.objects.create(user=user, active=True)

    # fire the allauth signal the change-password view emits
    password_changed.send(sender=user.__class__, request=None, user=user)

    token.refresh_from_db()
    assert token.active is False


def test_auditlog_records_event_changes():
    from auditlog.models import LogEntry

    event = EventFactory(name="Audited Event")
    event.name = "Audited Event v2"
    event.save()

    entries = LogEntry.objects.get_for_object(event)
    assert entries.filter(action=LogEntry.Action.UPDATE).exists()
