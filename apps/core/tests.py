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


def test_home_shows_future_public_events_and_active_chapter_count(client):
    chapter = ChapterFactory(active=True)
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

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert future in response.context["events"]
    assert past not in response.context["events"]
    assert response.context["active_chapters_count"] == Chapter.objects.filter(active=True).count()
    assert response.context["active_chapters_count"] == 1


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
