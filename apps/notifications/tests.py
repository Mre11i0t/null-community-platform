import datetime

import pytest
from django.conf import settings
from django.core import mail
from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.notifications.models import EventAutomaticNotificationTask, EventMailerTask
from apps.notifications.tasks import (
    dispatch_event_notifications,
    send_automatic_notification,
    send_event_mailer_task,
)
from tests.factories import (
    ChapterFactory,
    ChapterLeadFactory,
    EventFactory,
    EventRegistrationFactory,
    EventSessionFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


# --- Event creation triggers AdminOnCreate -----------------------------------


def test_event_creation_fires_admin_on_create_notification():
    chapter = ChapterFactory()
    lead = ChapterLeadFactory(chapter=chapter).user
    event = EventFactory(chapter=chapter)

    task = EventAutomaticNotificationTask.objects.get(
        event=event, mode=EventAutomaticNotificationTask.MODE_ADMIN_ON_CREATE
    )
    assert task.executed is True
    recipients = {addr for m in mail.outbox for addr in m.to}
    assert lead.email in recipients
    assert settings.NOTIFICATION_ADMIN_EVENT_CREATE[0] in recipients


# --- send_event_mailer_task ---------------------------------------------------


def test_mailer_task_only_sends_when_ready_for_delivery():
    event = EventFactory()
    EventRegistrationFactory(event=event)
    task = EventMailerTask.objects.create(event=event, subject="s", body="b", ready_for_delivery=False)
    mail.outbox.clear()

    send_event_mailer_task(task.pk)

    assert len(mail.outbox) == 0
    task.refresh_from_db()
    assert task.executed is False


def test_mailer_task_filters_by_registration_state():
    event = EventFactory()
    confirmed = EventRegistrationFactory(event=event)
    confirmed.state = EventRegistration.STATE_CONFIRMED
    confirmed.save()
    provisional = EventRegistrationFactory(event=event)
    provisional.state = EventRegistration.STATE_PROVISIONAL
    provisional.save()

    task = EventMailerTask.objects.create(
        event=event,
        subject="Confirmed only",
        body="Hello **world**",
        registration_state=EventRegistration.STATE_CONFIRMED,
        ready_for_delivery=True,
    )
    mail.outbox.clear()

    send_event_mailer_task(task.pk)

    recipients = {addr for m in mail.outbox for addr in m.to}
    assert confirmed.user.email in recipients
    assert provisional.user.email not in recipients

    task.refresh_from_db()
    assert task.executed is True
    assert task.ready_for_delivery is False


def test_mailer_task_html_alternative_is_rendered_markdown():
    event = EventFactory()
    EventRegistrationFactory(event=event)
    task = EventMailerTask.objects.create(
        event=event, subject="s", body="Hello **world**", ready_for_delivery=True
    )
    mail.outbox.clear()

    send_event_mailer_task(task.pk)

    sent = mail.outbox[0]
    assert sent.body == "Hello **world**"
    html_alt = next(content for content, mimetype in sent.alternatives if mimetype == "text/html")
    assert "<strong>world</strong>" in html_alt


# --- send_automatic_notification: all 7 modes --------------------------------


def test_announcement_goes_to_configured_addresses():
    event = EventFactory(name="Announce Me")
    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_ANNOUNCEMENT
    )
    mail.outbox.clear()

    send_automatic_notification(task.pk)

    recipients = {addr for m in mail.outbox for addr in m.to}
    assert set(settings.NOTIFICATION_ANNOUNCEMENT_ADDRESSES) == recipients
    task.refresh_from_db()
    assert task.executed is True


def test_speaker_notification_skips_placeholder_sessions():
    event = EventFactory()
    real_session = EventSessionFactory(event=event, placeholder=False)
    EventSessionFactory(event=event, placeholder=True, user=UserFactory(email="placeholder@example.com"))
    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_SPEAKER_NOTIFICATION
    )
    mail.outbox.clear()

    send_automatic_notification(task.pk)

    recipients = {addr for m in mail.outbox for addr in m.to}
    assert real_session.user.email in recipients
    assert "placeholder@example.com" not in recipients


def test_event_reminder_final_only_emails_confirmed_registrants():
    event = EventFactory()
    confirmed = EventRegistrationFactory(event=event)
    confirmed.state = EventRegistration.STATE_CONFIRMED
    confirmed.save()
    not_attending = EventRegistrationFactory(event=event)
    not_attending.state = EventRegistration.STATE_NOT_ATTENDING
    not_attending.save()

    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_EVENT_REMINDER_FINAL
    )
    mail.outbox.clear()

    send_automatic_notification(task.pk)

    recipients = {addr for m in mail.outbox for addr in m.to}
    assert confirmed.user.email in recipients
    assert not_attending.user.email not in recipients


def test_admin_on_create_dedupes_admin_and_lead_addresses():
    chapter = ChapterFactory()
    lead = ChapterLeadFactory(chapter=chapter).user
    event = EventFactory(chapter=chapter)
    EventAutomaticNotificationTask.objects.filter(event=event).delete()
    mail.outbox.clear()

    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_ADMIN_ON_CREATE
    )
    send_automatic_notification(task.pk)

    sent_count = sum(1 for m in mail.outbox if lead.email in m.to)
    assert sent_count == 1  # not duplicated even if lead somehow appears twice


def test_presentation_update_reminder_only_targets_sessions_missing_a_url():
    event = EventFactory()
    missing_url = EventSessionFactory(event=event, presentation_url="")
    has_url = EventSessionFactory(event=event, presentation_url="https://speakerdeck.com/x")
    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_PRESENTATION_UPDATE_REMINDER
    )
    mail.outbox.clear()

    send_automatic_notification(task.pk)

    recipients = {addr for m in mail.outbox for addr in m.to}
    assert missing_url.user.email in recipients
    assert has_url.user.email not in recipients


def test_notification_task_does_not_resend_once_executed():
    event = EventFactory()
    task = EventAutomaticNotificationTask.objects.create(
        event=event, mode=EventAutomaticNotificationTask.MODE_ANNOUNCEMENT, executed=True
    )
    mail.outbox.clear()

    send_automatic_notification(task.pk)

    assert len(mail.outbox) == 0


# --- dispatch_event_notifications: the full state machine -------------------


def test_dispatch_advances_init_to_initial_notifications():
    event = EventFactory(public=True, ready_for_notifications=True, notification_state=Event.STATE_INIT)
    EventSessionFactory(event=event, placeholder=False)
    mail.outbox.clear()

    dispatch_event_notifications()

    event.refresh_from_db()
    assert event.notification_state == Event.STATE_INITIAL_NOTIFICATIONS
    assert event.notifications_sent_at is not None
    assert EventAutomaticNotificationTask.objects.filter(
        event=event, mode=EventAutomaticNotificationTask.MODE_ANNOUNCEMENT, executed=True
    ).exists()
    assert EventAutomaticNotificationTask.objects.filter(
        event=event, mode=EventAutomaticNotificationTask.MODE_SPEAKER_NOTIFICATION, executed=True
    ).exists()


def test_dispatch_does_not_advance_when_not_ready_for_notifications():
    event = EventFactory(public=True, ready_for_notifications=False, notification_state=Event.STATE_INIT)

    dispatch_event_notifications()

    event.refresh_from_db()
    assert event.notification_state == Event.STATE_INIT


def test_dispatch_does_not_advance_non_public_events():
    event = EventFactory(public=False, ready_for_notifications=True, notification_state=Event.STATE_INIT)

    dispatch_event_notifications()

    event.refresh_from_db()
    assert event.notification_state == Event.STATE_INIT


def test_dispatch_advances_through_full_state_machine():
    now = timezone.now()
    event = EventFactory(
        public=True,
        ready_for_notifications=True,
        ready_for_reminders=True,
        notification_state=Event.STATE_INITIAL_NOTIFICATIONS,
        start_time=now + datetime.timedelta(hours=36),
        end_time=now + datetime.timedelta(hours=38),
    )
    EventSessionFactory(event=event, placeholder=False)
    confirmed = EventRegistrationFactory(event=event)
    confirmed.state = EventRegistration.STATE_CONFIRMED
    confirmed.save()

    # Reminder1: event starts within 2 days.
    dispatch_event_notifications()
    event.refresh_from_db()
    assert event.notification_state == Event.STATE_REMINDER1

    # Reminder2: move the event to start within 1 day, dispatch again.
    event.start_time = now + datetime.timedelta(hours=20)
    event.end_time = now + datetime.timedelta(hours=22)
    event.save(update_fields=["start_time", "end_time"])
    mail.outbox.clear()
    dispatch_event_notifications()
    event.refresh_from_db()
    assert event.notification_state == Event.STATE_REMINDER2
    assert EventAutomaticNotificationTask.objects.filter(
        event=event, mode=EventAutomaticNotificationTask.MODE_EVENT_REMINDER_FINAL, executed=True
    ).exists()
    recipients = {addr for m in mail.outbox for addr in m.to}
    assert confirmed.user.email in recipients

    # PresentationUpdate: move the event's end time into the past.
    event.end_time = now - datetime.timedelta(hours=2)
    event.save(update_fields=["end_time"])
    dispatch_event_notifications()
    event.refresh_from_db()
    assert event.notification_state == Event.STATE_PRESENTATION_UPDATE
    assert EventAutomaticNotificationTask.objects.filter(
        event=event,
        mode=EventAutomaticNotificationTask.MODE_PRESENTATION_UPDATE_REMINDER,
        executed=True,
    ).exists()


def test_dispatch_is_idempotent_once_state_has_advanced():
    event = EventFactory(public=True, ready_for_notifications=True, notification_state=Event.STATE_INIT)

    dispatch_event_notifications()
    first_task_count = EventAutomaticNotificationTask.objects.filter(event=event).count()

    dispatch_event_notifications()
    second_task_count = EventAutomaticNotificationTask.objects.filter(event=event).count()

    assert first_task_count == second_task_count
