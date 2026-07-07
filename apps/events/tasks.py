from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Event, EventRegistration

# Grace period after end_time before no-shows are marked Absent, so a
# scanner still open while people trickle out doesn't lose late check-ins.
AUTO_ABSENT_GRACE = timedelta(hours=1)


@shared_task
def auto_mark_absent():
    """Rev 3: for events that opted in (auto_absent_enabled — independent
    of check_in_enabled by design, but meaningless without it since nobody
    can have checked in), flip confirmed-but-never-checked-in registrations
    to Absent once the event is over. Runs from beat; idempotent via
    auto_absent_processed_at."""
    cutoff = timezone.now() - AUTO_ABSENT_GRACE
    events = Event.objects.alive().filter(
        auto_absent_enabled=True,
        check_in_enabled=True,
        auto_absent_processed_at__isnull=True,
        end_time__lt=cutoff,
    )
    processed = 0
    for event in events:
        event.event_registrations.filter(
            state=EventRegistration.STATE_CONFIRMED, checked_in_at__isnull=True
        ).update(state=EventRegistration.STATE_ABSENT, updated_at=timezone.now())
        event.auto_absent_processed_at = timezone.now()
        event.save(update_fields=["auto_absent_processed_at"])
        processed += 1
    return processed
