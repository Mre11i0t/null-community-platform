"""Rev 3 gamification — computed, not stored.

Points and badges derive live from what the member actually did
(attendance, talks, co-talks), so there's no ledger to corrupt or
backfill and no way for the numbers to drift from reality. Extends the
existing UserAchievement display (original gap #8's achievements side).
"""

from django.utils import timezone

POINTS = {"attended": 10, "talk": 50, "co_talk": 25}

BADGES = [
    # (slug, label, test) — evaluated against the stats dict below
    ("first-talk", "First Talk", lambda s: s["talks"] >= 1),
    ("veteran-speaker", "Veteran Speaker", lambda s: s["talks"] >= 5),
    ("regular", "Regular", lambda s: s["attended"] >= 5),
    ("community-pillar", "Community Pillar", lambda s: s["attended"] >= 25),
]


def user_stats(user, chapter=None):
    from apps.events.models import EventRegistration

    registrations = user.event_registrations.filter(
        state=EventRegistration.STATE_CONFIRMED, event__end_time__lt=timezone.now()
    )
    talks = user.event_sessions.filter(placeholder=False, deleted_at__isnull=True)
    co_talks = user.co_speaker_sessions.filter(deleted_at__isnull=True)
    if chapter is not None:
        registrations = registrations.filter(event__chapter=chapter)
        talks = talks.filter(event__chapter=chapter)
        co_talks = co_talks.filter(event__chapter=chapter)
    return {
        "attended": registrations.count(),
        "talks": talks.count(),
        "co_talks": co_talks.count(),
    }


def user_points(user, chapter=None):
    stats = user_stats(user, chapter)
    return (
        stats["attended"] * POINTS["attended"]
        + stats["talks"] * POINTS["talk"]
        + stats["co_talks"] * POINTS["co_talk"]
    )


def user_badges(user):
    stats = user_stats(user)
    return [{"slug": slug, "label": label} for slug, label, test in BADGES if test(stats)]


def chapter_leaderboard(chapter, limit=20):
    """Top members by points within one chapter. Computed over everyone
    who ever held a confirmed seat there — fine at community scale."""
    from apps.accounts.models import User
    from apps.events.models import EventRegistration

    user_ids = (
        EventRegistration.objects.filter(
            event__chapter=chapter, state=EventRegistration.STATE_CONFIRMED
        )
        .values_list("user_id", flat=True)
        .distinct()
    )
    rows = []
    for user in User.objects.filter(id__in=user_ids, is_active=True):
        points = user_points(user, chapter)
        if points:
            rows.append({"user": user, "points": points})
    rows.sort(key=lambda row: -row["points"])
    return rows[:limit]
