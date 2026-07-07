"""Aggregations for the analytics dashboards and monthly report."""

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.events.models import Event, EventRegistration, EventSession

from .models import PageVisit


def traffic_by_host(days=30):
    since = timezone.now() - timedelta(days=days)
    return list(
        PageVisit.objects.filter(created_at__gte=since)
        .values("host")
        .annotate(hits=Count("id"))
        .order_by("-hits")
    )


def top_referrers(days=30, chapter=None, limit=15):
    since = timezone.now() - timedelta(days=days)
    qs = PageVisit.objects.filter(created_at__gte=since).exclude(referrer_domain="")
    if chapter is not None:
        qs = qs.filter(chapter=chapter)
    return list(qs.values("referrer_domain").annotate(hits=Count("id")).order_by("-hits")[:limit])


def chapter_traffic(chapter, days=30):
    since = timezone.now() - timedelta(days=days)
    return PageVisit.objects.filter(chapter=chapter, created_at__gte=since).count()


def attendance_funnel(event):
    """registered → confirmed → checked-in for one event."""
    registrations = event.event_registrations
    return {
        "registered": registrations.count(),
        "confirmed": registrations.filter(
            state__in=[EventRegistration.STATE_CONFIRMED, EventRegistration.STATE_ABSENT]
        ).count(),
        "checked_in": registrations.filter(checked_in_at__isnull=False).count(),
    }


def chapter_health(chapter, days=365):
    """Lead-facing chapter vitals: RSVP volume, repeat-attendee rate,
    new-member rate, and speaker pipeline depth."""
    since = timezone.now() - timedelta(days=days)
    events = Event.objects.alive().filter(chapter=chapter, start_time__gte=since)
    registrations = EventRegistration.objects.filter(event__in=events)

    user_counts = registrations.values("user_id").annotate(n=Count("id"))
    total_attendees = len(user_counts)
    repeat_attendees = sum(1 for row in user_counts if row["n"] > 1)

    new_members = 0
    for row in user_counts:
        first = (
            EventRegistration.objects.filter(user_id=row["user_id"])
            .order_by("created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if first and first >= since:
            new_members += 1

    return {
        "events": events.count(),
        "registrations": registrations.count(),
        "unique_attendees": total_attendees,
        "repeat_rate": round(100 * repeat_attendees / total_attendees) if total_attendees else 0,
        "new_members": new_members,
    }


def speaker_stats(chapter, days=365):
    """First-time vs repeat speakers + sessions missing slides/video."""
    since = timezone.now() - timedelta(days=days)
    sessions = EventSession.objects.alive().filter(
        event__chapter=chapter, event__start_time__gte=since, placeholder=False
    )
    speaker_ids = set(sessions.values_list("user_id", flat=True))
    first_time = 0
    for user_id in speaker_ids:
        earliest = (
            EventSession.objects.alive()
            .filter(user_id=user_id, placeholder=False)
            .order_by("start_time")
            .values_list("start_time", flat=True)
            .first()
        )
        if earliest and earliest >= since:
            first_time += 1

    past_sessions = sessions.filter(event__end_time__lt=timezone.now())
    return {
        "sessions": sessions.count(),
        "speakers": len(speaker_ids),
        "first_time_speakers": first_time,
        "missing_slides": past_sessions.filter(presentation_url="").count(),
        "missing_video": past_sessions.filter(video_url="").count(),
    }
