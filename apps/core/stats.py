"""Ports app/models/stat.rb — a small non-persisted aggregation object
used by the yearly community stats page (StatsController#show)."""

import datetime

from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import Event, EventRegistration, EventSession


class Stat:
    def __init__(self, year, chapter=None):
        self.year = year
        self.chapter = chapter

    def events(self):
        start = timezone.make_aware(datetime.datetime(self.year, 1, 1))
        end = timezone.make_aware(datetime.datetime(self.year + 1, 1, 1))
        qs = Event.objects.filter(start_time__gte=start, start_time__lt=end, public=True)
        if self.chapter is not None:
            qs = qs.filter(chapter=self.chapter)
        return qs

    def event_sessions(self):
        return EventSession.objects.filter(event__in=self.events(), placeholder=False)

    def event_registrations(self):
        return EventRegistration.objects.filter(
            event__in=self.events(), state=EventRegistration.STATE_CONFIRMED
        )

    def speakers(self):
        return User.objects.filter(pk__in=self.event_sessions().values_list("user_id", flat=True)).distinct()

    def top_speakers(self, n=5):
        rows = (
            self.event_sessions()
            .values("user_id")
            .annotate(session_count=Count("user_id"))
            .order_by("-session_count")[:n]
        )
        users = {u.pk: u for u in User.objects.filter(pk__in=[r["user_id"] for r in rows])}
        return [(users[r["user_id"]], r["session_count"]) for r in rows if r["user_id"] in users]
