"""Rev 3 dev seed — builds on seed_dev_data.py with data that exercises
the new machinery: chapter sites (subdomains), check-in flags, a
full-capacity event (waitlist), an invite-only event (approval queue),
a just-ended event (feedback/auto-absent sweeps), CFP proposals,
starred sessions, custom questions, and webhook/preference rows.

Run with: python manage.py shell < scripts/seed_rev3_data.py
Idempotent — safe to re-run.
"""
import os
import secrets
from datetime import timedelta

from django.utils import timezone

# Never bake "password" into seeded accounts. Pin a value with SEED_PASSWORD in
# the env for reproducible logins, otherwise a strong one is generated + printed.
SEED_PASSWORD = os.environ.get("SEED_PASSWORD") or ("null-seed-" + secrets.token_urlsafe(9))

from apps.accounts.models import User
from apps.chapters.models import Chapter, ChapterLead
from apps.events.models import Event, EventRegistration, EventSession, EventType, Venue
from apps.proposals.models import SessionProposal

now = timezone.now()

# The chapter that gets the lead, venue, demo events, sessions, and proposal.
# The other seeded chapters stay as empty shells (still routable, no content).
# Change this to re-home the demo onto a different city, then re-seed.
PRIMARY_CHAPTER = "Bangalore"


def make_user(email, name, password=None):
    password = password or SEED_PASSWORD
    user, _ = User.objects.get_or_create(email=email, defaults={"name": name, "is_active": True})
    user.set_password(password)
    user.save()
    user.acknowledge_coc()
    return user


lead_user = make_user("lead@example.com", "Lakshmi Lead")
speaker = make_user("speaker@example.com", "Jane Speaker")
members = [make_user(f"member{i}@example.com", f"Member {i}") for i in range(1, 7)]
admin = make_user("admin@example.com", "Adi Admin")
admin.is_staff = True
admin.is_superuser = True
admin.save()

meetup_type, _ = EventType.objects.get_or_create(
    name="Monthly Meet", defaults={"description": "Regular monthly meetup", "public": True}
)
invite_type, _ = EventType.objects.get_or_create(
    name="Red Team Workshop",
    defaults={"description": "Hands-on, invite only", "public": True, "invitation_required": True},
)

chapters = {}
for city in ("Delhi", "Bangalore", "Goa"):
    chapter, _ = Chapter.objects.get_or_create(
        name=city,
        defaults={
            "code": city.lower()[:3],
            "description": f"The {city} chapter of null — the open security community.",
            "city": city,
            "country": "India",
            "active": True,
        },
    )
    chapters[city] = chapter

ChapterLead.objects.get_or_create(user=lead_user, chapter=chapters[PRIMARY_CHAPTER], defaults={"active": True})

venue, _ = Venue.objects.get_or_create(
    chapter=chapters[PRIMARY_CHAPTER],
    name="Hackspace Auditorium",
    defaults={"address": f"42 Cyber Street, {PRIMARY_CHAPTER}", "contact_name": "Front Desk"},
)

# 1. Upcoming event with check-in + auto-absent + custom questions + deadline
checkin_event, _ = Event.objects.get_or_create(
    name="July Meetup — Check-in Demo",
    chapter=chapters[PRIMARY_CHAPTER],
    defaults=dict(
        venue=venue,
        event_type=meetup_type,
        public=True,
        start_time=now + timedelta(days=3),
        end_time=now + timedelta(days=3, hours=3),
        registration_start_time=now - timedelta(days=2),
        registration_end_time=now + timedelta(days=2),
        accepting_registration=True,
        check_in_enabled=True,
        auto_absent_enabled=True,
        cancellation_deadline_hours=12,
        custom_questions=[
            {"label": "T-shirt size", "required": True},
            {"label": "Dietary needs", "required": False},
        ],
    ),
)
for member in members[:3]:
    EventRegistration.objects.get_or_create(event=checkin_event, user=member)

# 2. Full event -> waitlist demo (cap 2, 3 registrants)
full_event, _ = Event.objects.get_or_create(
    name="Packed Workshop — Waitlist Demo",
    chapter=chapters[PRIMARY_CHAPTER],
    defaults=dict(
        venue=venue,
        event_type=meetup_type,
        public=True,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=3),
        registration_start_time=now - timedelta(days=2),
        registration_end_time=now + timedelta(days=6),
        accepting_registration=True,
        max_registration=2,
    ),
)
for member in members[:3]:
    EventRegistration.objects.get_or_create(event=full_event, user=member)

# 3. Invite-only event -> approval queue demo
invite_event, _ = Event.objects.get_or_create(
    name="Red Team Night — Approval Demo",
    chapter=chapters[PRIMARY_CHAPTER],
    defaults=dict(
        venue=venue,
        event_type=invite_type,
        public=True,
        start_time=now + timedelta(days=10),
        end_time=now + timedelta(days=10, hours=4),
        registration_start_time=now - timedelta(days=1),
        registration_end_time=now + timedelta(days=9),
        accepting_registration=True,
    ),
)
for member in members[3:6]:
    EventRegistration.objects.get_or_create(event=invite_event, user=member)

# 4. Just-ended event -> feedback + auto-absent sweep targets
ended_event, _ = Event.objects.get_or_create(
    name="June Meetup — Just Ended",
    chapter=chapters[PRIMARY_CHAPTER],
    defaults=dict(
        venue=venue,
        event_type=meetup_type,
        public=True,
        start_time=now - timedelta(hours=10),
        end_time=now - timedelta(hours=7),
        check_in_enabled=True,
        auto_absent_enabled=True,
    ),
)
attended, _ = EventRegistration.objects.get_or_create(event=ended_event, user=members[0])
attended.set_state(EventRegistration.STATE_CONFIRMED)
attended.check_in()
no_show, _ = EventRegistration.objects.get_or_create(event=ended_event, user=members[1])
no_show.set_state(EventRegistration.STATE_CONFIRMED)

# sessions + tags + co-speaker
session, _ = EventSession.objects.get_or_create(
    event=checkin_event,
    user=speaker,
    name="Breaking Android 16 Sandboxing",
    defaults=dict(
        description="Deep dive into the new sandbox internals.",
        start_time=checkin_event.start_time + timedelta(minutes=30),
        end_time=checkin_event.start_time + timedelta(minutes=90),
    ),
)
session.tags.add("android", "mobile")
session.co_speakers.add(members[0])

past_session, _ = EventSession.objects.get_or_create(
    event=ended_event,
    user=speaker,
    name="OSINT Pipelines on a Budget",
    defaults=dict(
        description="Free-tier OSINT automation.",
        start_time=ended_event.start_time + timedelta(minutes=15),
        end_time=ended_event.start_time + timedelta(minutes=60),
        presentation_url="https://slides.example.com/osint",
    ),
)
past_session.tags.add("osint")

SessionProposal.objects.get_or_create(
    chapter=chapters[PRIMARY_CHAPTER],
    user=members[2],
    session_topic="Kubernetes Attack Paths",
    defaults={"event_type": meetup_type, "session_description": "K8s privilege escalation walkthrough."},
)

print("Seeded Rev 3 data:")
print(f"  primary (populated) chapter: {PRIMARY_CHAPTER} (subdomain {chapters[PRIMARY_CHAPTER].subdomain})")
print(f"  chapters: {', '.join(c.subdomain for c in chapters.values())} (others are empty shells)")
print(f"  users: lead@example.com / speaker@example.com / member1..6@example.com / admin@example.com")
print(f"  seed password (all seeded users): {SEED_PASSWORD}  (pin via SEED_PASSWORD env)")
print(f"  events: #{checkin_event.pk} check-in, #{full_event.pk} waitlist, #{invite_event.pk} approval, #{ended_event.pk} ended")
