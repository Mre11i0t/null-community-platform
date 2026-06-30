"""Quick dev-only seed script — minimal data to exercise every route in
the vertical slice (home, /upcoming, chapter list/detail, event detail,
session detail, public profile, CMS page), including an EventSession
and EventRegistration so those code paths actually render.
Run with: python manage.py shell < scripts/seed_dev_data.py
"""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.chapters.models import Chapter, ChapterLead
from apps.content.models import Page
from apps.events.models import Event, EventRegistration, EventSession, EventType, Venue

speaker, _ = User.objects.get_or_create(
    email="speaker@example.com", defaults={"name": "Jane Speaker", "is_active": True}
)
speaker.set_password("password")
speaker.save()

chapter, _ = Chapter.objects.get_or_create(
    name="Pune",
    defaults={
        "code": "pune",
        "description": "The Pune chapter of null — the open security community.",
        "city": "Pune",
        "state": "Maharashtra",
        "country": "India",
        "active": True,
    },
)

ChapterLead.objects.get_or_create(user=speaker, chapter=chapter, defaults={"active": True})

venue, _ = Venue.objects.get_or_create(
    chapter=chapter,
    name="Test Auditorium",
    defaults={
        "address": "123 Test Street, Pune",
        "contact_name": "Jane Speaker",
        "contact_email": "speaker@example.com",
    },
)

event_type, _ = EventType.objects.get_or_create(
    name="Monthly Meet",
    defaults={"description": "Regular monthly chapter meetup.", "invitation_required": False},
)

event, _ = Event.objects.get_or_create(
    name="Pune null Monthly Meet",
    chapter=chapter,
    defaults={
        "description": "A talk on web security.",
        "venue": venue,
        "event_type": event_type,
        "public": True,
        "start_time": timezone.now() + timedelta(days=7),
        "end_time": timezone.now() + timedelta(days=7, hours=3),
        "max_registration": 0,
    },
)

attendee, _ = User.objects.get_or_create(
    email="attendee@example.com", defaults={"name": "Alex Attendee", "is_active": True}
)
attendee.set_password("password")
attendee.save()

session, _ = EventSession.objects.get_or_create(
    event=event,
    user=speaker,
    name="Intro to Web Security",
    defaults={
        "description": "A beginner-friendly walkthrough of the OWASP Top 10.",
        "session_type": "Talk",
        "start_time": event.start_time,
        "end_time": event.start_time + timedelta(hours=1),
        "presentation_url": "https://slideshare.net/example/intro-websec",
        "video_url": "https://youtube.com/watch?v=example",
    },
)

EventRegistration.objects.get_or_create(
    event=event,
    user=attendee,
    defaults={"state": EventRegistration.STATE_CONFIRMED, "accepted": True},
)

page, _ = Page.objects.get_or_create(
    name="how-to-start-a-chapter",
    defaults={
        "title": "How to Start a Chapter",
        "description": "Guide for starting a new chapter",
        "navigation_name": "Start a Chapter",
        "content": "# Starting a Chapter\n\nGet 3 interested people together and reach out!",
        "published": True,
        "slug": "3-how-to-start-a-chapter",
    },
)

print(
    f"Seeded: chapter={chapter.pk} event={event.pk} session={session.pk} "
    f"speaker={speaker.pk} attendee={attendee.pk} page={page.slug}"
)
