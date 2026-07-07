import datetime

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.analytics.models import PageVisit
from apps.analytics.tasks import send_monthly_chapter_reports
from tests.factories import (
    ChapterFactory,
    ChapterLeadFactory,
    EventFactory,
    EventRegistrationFactory,
)

pytestmark = pytest.mark.django_db


def test_page_visit_recorded_with_host_chapter_and_referrer(client):
    chapter = ChapterFactory(name="Delhi")
    client.get(
        "/",
        HTTP_HOST="delhi.localhost",
        HTTP_REFERER="https://twitter.com/nulldelhi/status/1",
    )
    visit = PageVisit.objects.get()
    assert visit.host == "delhi.localhost"
    assert visit.chapter == chapter
    assert visit.referrer_domain == "twitter.com"


def test_internal_referrers_and_bots_and_utm(client):
    ChapterFactory(name="Delhi")

    # internal navigation → no referrer recorded
    client.get("/", HTTP_HOST="delhi.localhost", HTTP_REFERER="http://delhi.localhost/upcoming")
    assert PageVisit.objects.get().referrer_domain == ""

    # bots skipped entirely
    PageVisit.objects.all().delete()
    client.get("/", HTTP_HOST="delhi.localhost", HTTP_USER_AGENT="Googlebot/2.1")
    assert PageVisit.objects.count() == 0

    # UTM captured
    client.get("/?utm_source=newsletter&utm_medium=email", HTTP_HOST="delhi.localhost")
    assert PageVisit.objects.get().utm_source == "newsletter"


def test_skip_paths_not_recorded(client):
    client.get("/domains/check", {"domain": "localhost"})
    assert PageVisit.objects.count() == 0


def test_analytics_dashboard_for_lead(client):
    lead = ChapterLeadFactory()
    event = EventFactory(
        chapter=lead.chapter,
        start_time=timezone.now() - datetime.timedelta(days=2),
        end_time=timezone.now() - datetime.timedelta(days=2, hours=-2),
    )
    registration = EventRegistrationFactory(event=event)
    registration.check_in()
    PageVisit.objects.create(host="x.localhost", path="/", chapter=lead.chapter, referrer_domain="news.ycombinator.com")

    client.force_login(lead.user)
    response = client.get(reverse("leads:analytics_dashboard"))

    assert response.status_code == 200
    card = next(c for c in response.context["chapter_cards"] if c["chapter"] == lead.chapter)
    assert card["traffic"] == 1
    assert card["referrers"][0]["referrer_domain"] == "news.ycombinator.com"
    funnel = next(f for f in card["funnels"] if f["event"] == event)
    assert funnel["registered"] == 1 and funnel["checked_in"] == 1


def test_monthly_report_emails_chapter_leads():
    lead = ChapterLeadFactory()
    EventFactory(
        chapter=lead.chapter,
        start_time=timezone.now() - datetime.timedelta(days=5),
        end_time=timezone.now() - datetime.timedelta(days=5, hours=-2),
    )
    mail.outbox.clear()

    assert send_monthly_chapter_reports() >= 1
    report = next(m for m in mail.outbox if lead.user.email in m.to)
    assert "Monthly chapter report" in report.subject
    assert "Events held: 1" in report.body
