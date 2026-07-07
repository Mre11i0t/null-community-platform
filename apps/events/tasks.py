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


@shared_task
def send_feedback_requests():
    """Rev 3: N hours after an event ends (FEEDBACK_DELAY_HOURS), email
    everyone who actually held a seat asking for a 1-5 rating. Honors
    the email_feedback_requests preference; idempotent via
    Event.feedback_requested_at."""
    from django.conf import settings
    from django.core.mail import send_mail

    from apps.notifications.models import NotificationPreference

    cutoff = timezone.now() - timedelta(hours=settings.FEEDBACK_DELAY_HOURS)
    events = Event.objects.alive().filter(
        public=True, feedback_requested_at__isnull=True, end_time__lt=cutoff,
        end_time__gt=timezone.now() - timedelta(days=14),  # don't spam ancient events on first deploy
    )
    processed = 0
    for event in events:
        recipients = event.event_registrations.filter(
            state__in=[EventRegistration.STATE_CONFIRMED, EventRegistration.STATE_ABSENT]
        ).select_related("user")
        for registration in recipients:
            if not NotificationPreference.for_user(registration.user).email_feedback_requests:
                continue
            send_mail(
                subject=f"[null] How was {event.name}?",
                message=(
                    f"Thanks for being part of {event.descriptive_name()}!\n\n"
                    f"Two clicks of feedback help the organizers make the next one better:\n"
                    f"{settings.SITE_BASE_URL}/events/{event.pk}/feedback/\n"
                ),
                from_email=None,
                recipient_list=[registration.user.email],
                fail_silently=True,
            )
        event.feedback_requested_at = timezone.now()
        event.save(update_fields=["feedback_requested_at"])
        processed += 1
    return processed
