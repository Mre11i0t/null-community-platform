"""Celery tasks replacing the original Resque jobs + Resque Scheduler.

Ports app/models/event_mailer_task.rb#do_background, the six
EventAutomaticNotificationTask#do_background branches, and the
EventNotification state machine (app/models/event_notification.rb) that
drives when those automatic notifications fire.

Google Calendar sync and Twitter/IFTTT posting are left as documented
stubs below — the original's GoogleAPI::* and IftttMailer classes need
OAuth service-account credentials and an IFTTT webhook key that aren't
available in this environment.
"""

import markdown as md
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.notifications.models import EventAutomaticNotificationTask, EventMailerTask


def _abs_url(path):
    return f"{settings.SITE_BASE_URL}{path}"


def _event_url(event):
    return _abs_url(reverse("events:detail", args=[event.pk]))


def _session_url(session):
    return _abs_url(reverse("events:session_detail", args=[session.pk]))


@shared_task
def send_event_mailer_task(task_id: int) -> None:
    """Ports EventMailerTask#do_background — a leader-authored custom
    email blast to a filtered subset of an event's registrations."""
    try:
        task = EventMailerTask.objects.select_related("event").get(pk=task_id)
    except EventMailerTask.DoesNotExist:
        return
    if task.executed or not task.ready_for_delivery:
        return

    registrations = task.event.event_registrations.select_related("user")
    if task.registration_state:
        registrations = registrations.filter(state=task.registration_state)

    html_body = md.markdown(task.body, extensions=["fenced_code", "nl2br"])
    for registration in registrations:
        if not registration.user_id:
            continue
        message = EmailMultiAlternatives(
            subject=task.subject,
            body=task.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[registration.user.email],
        )
        message.attach_alternative(html_body, "text/html")
        message.send()

    task.executed = True
    task.ready_for_delivery = False
    task.save(update_fields=["executed", "ready_for_delivery"])


@shared_task
def send_automatic_notification(task_id: int) -> None:
    """Ports EventAutomaticNotificationTask#do_background's mode dispatch."""
    try:
        task = EventAutomaticNotificationTask.objects.select_related(
            "event", "event__chapter", "event__event_type", "event__venue"
        ).get(pk=task_id)
    except EventAutomaticNotificationTask.DoesNotExist:
        return
    if task.executed:
        return

    handlers = {
        EventAutomaticNotificationTask.MODE_ANNOUNCEMENT: _send_announcement,
        EventAutomaticNotificationTask.MODE_SPEAKER_NOTIFICATION: _send_speaker_notification,
        EventAutomaticNotificationTask.MODE_EVENT_REMINDER: _send_event_reminder,
        EventAutomaticNotificationTask.MODE_EVENT_REMINDER_FINAL: _send_rsvp_reminders,
        EventAutomaticNotificationTask.MODE_SPEAKER_REMINDER: _send_speaker_reminder,
        EventAutomaticNotificationTask.MODE_ADMIN_ON_CREATE: _send_admin_on_create,
        EventAutomaticNotificationTask.MODE_PRESENTATION_UPDATE_REMINDER: _send_presentation_update_reminder,
    }
    handler = handlers.get(task.mode)
    if handler:
        handler(task.event)

    task.executed = True
    task.save(update_fields=["executed"])


def _event_context(event):
    return {
        "event": event,
        "sessions": event.event_sessions.order_by("start_time"),
        "invite_only": event.invite_only(),
        "event_url": _event_url(event),
    }


def _send_announcement(event):
    """Ports EventAutomaticNotificationTask#event_announcement, plus the
    Rev 3 broadcast fan-out (Discord/Slack/Telegram/X) that replaces the
    original's IFTTT tweet."""
    from .broadcast import broadcast

    body = render_to_string("notifications/emails/announcement.txt", _event_context(event))
    subject = f"[Announcement] {event.descriptive_name()}"
    for address in settings.NOTIFICATION_ANNOUNCEMENT_ADDRESSES:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [address])
    broadcast(
        f"\U0001F4E2 {event.descriptive_name()} — registrations open! {_event_url(event)}"
    )


def _send_event_reminder(event):
    """Ports EventAutomaticNotificationTask#event_reminder (Reminder1),
    plus the Rev 3 broadcast fan-out."""
    from .broadcast import broadcast

    body = render_to_string("notifications/emails/reminder.txt", _event_context(event))
    subject = f"[Reminder] {event.descriptive_name()}"
    for address in settings.NOTIFICATION_ANNOUNCEMENT_ADDRESSES:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [address])
    broadcast(f"\u23F0 This week: {event.descriptive_name()} {_event_url(event)}")


def _send_speaker_notification(event):
    """Ports EventAutomaticNotificationTask#speaker_notification."""
    from .models import NotificationPreference

    for session in event.event_sessions.filter(placeholder=False).select_related("user"):
        if not session.user_id:
            continue
        if not NotificationPreference.for_user(session.user).email_speaker_notifications:
            continue
        body = render_to_string(
            "notifications/emails/speaker_notification.txt",
            {"session": session, "session_url": _session_url(session)},
        )
        subject = f"[Notification] Speaker for {session.name}"
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [session.user.email])


def _send_speaker_reminder(event):
    """Ports EventAutomaticNotificationTask#speaker_reminder."""
    from .models import NotificationPreference

    for session in event.event_sessions.filter(placeholder=False).select_related("user"):
        if not session.user_id:
            continue
        if not NotificationPreference.for_user(session.user).email_speaker_notifications:
            continue
        body = render_to_string(
            "notifications/emails/speaker_reminder.txt",
            {"session": session, "session_url": _session_url(session)},
        )
        subject = f"[Reminder] Speaker for {session.name}"
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [session.user.email])


def _send_admin_on_create(event):
    """Ports EventAutomaticNotificationTask#admin_on_create_notify."""
    targets = list(settings.NOTIFICATION_ADMIN_EVENT_CREATE)
    targets += [u.email for u in event.chapter.leads()]
    targets = list(dict.fromkeys(targets))  # dedupe, preserve order

    body = render_to_string(
        "notifications/emails/admin_on_create.txt",
        {
            "event": event,
            "event_url": _event_url(event),
            "leads_event_url": _abs_url(reverse("leads:event_show", args=[event.pk])),
        },
    )
    subject = f"[Event Creation] New event created: {event.descriptive_name()}"
    for address in targets:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [address])


def _send_presentation_update_reminder(event):
    """Ports EventAutomaticNotificationTask#speaker_remind_presentation_update."""
    sessions = event.event_sessions.filter(placeholder=False, presentation_url="").select_related("user")
    for session in sessions:
        if not session.user_id:
            continue
        body = render_to_string(
            "notifications/emails/presentation_update.txt",
            {"session": session, "session_url": _session_url(session)},
        )
        subject = f"[Reminder] Presentation URL Update for: {session.name}"
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [session.user.email])


@shared_task
def dispatch_event_notifications() -> None:
    """Ports Event#setup_scheduled_tasks + the EventNotification state
    machine's before_transition hooks — replaces the original's one-shot
    Resque Scheduler jobs with a periodic sweep (see CELERY_BEAT_SCHEDULE)
    that advances each public event's notification_state when its time
    window is reached.

    Not started automatically in dev — there is no celery beat process
    running unless one is started separately (`celery -A config beat`).
    For manual testing, call this task directly.
    """
    from apps.events.models import Event

    now = timezone.now()

    init_events = Event.objects.filter(public=True, notification_state=Event.STATE_INIT, ready_for_notifications=True)
    for event in init_events:
        _create_and_run(event, EventAutomaticNotificationTask.MODE_ANNOUNCEMENT)
        _create_and_run(event, EventAutomaticNotificationTask.MODE_SPEAKER_NOTIFICATION)
        event.notification_state = Event.STATE_INITIAL_NOTIFICATIONS
        event.notifications_sent_at = now
        event.save(update_fields=["notification_state", "notifications_sent_at"])

    reminder1_events = Event.objects.filter(
        public=True,
        notification_state=Event.STATE_INITIAL_NOTIFICATIONS,
        ready_for_reminders=True,
        start_time__lte=now + timezone.timedelta(days=2),
    )
    for event in reminder1_events:
        _create_and_run(event, EventAutomaticNotificationTask.MODE_EVENT_REMINDER)
        _create_and_run(event, EventAutomaticNotificationTask.MODE_SPEAKER_REMINDER)
        event.notification_state = Event.STATE_REMINDER1
        event.save(update_fields=["notification_state"])

    reminder2_events = Event.objects.filter(
        public=True,
        notification_state=Event.STATE_REMINDER1,
        ready_for_reminders=True,
        start_time__lte=now + timezone.timedelta(days=1),
    )
    for event in reminder2_events:
        _create_and_run(event, EventAutomaticNotificationTask.MODE_EVENT_REMINDER_FINAL)
        event.notification_state = Event.STATE_REMINDER2
        event.save(update_fields=["notification_state"])

    presentation_events = Event.objects.filter(
        public=True,
        notification_state=Event.STATE_REMINDER2,
        ready_for_reminders=True,
        end_time__lte=now - timezone.timedelta(hours=1),
    )
    for event in presentation_events:
        _create_and_run(event, EventAutomaticNotificationTask.MODE_PRESENTATION_UPDATE_REMINDER)
        event.notification_state = Event.STATE_PRESENTATION_UPDATE
        event.save(update_fields=["notification_state"])


def _create_and_run(event, mode):
    task = EventAutomaticNotificationTask.objects.create(event=event, mode=mode)
    send_automatic_notification.delay(task.pk)


def _send_rsvp_reminders(event):
    """Ports EventAutomaticNotificationTask#rsvp_user_reminder
    (MODE_EVENT_REMINDER_FINAL) — sent directly to confirmed attendees
    at the Reminder2 transition."""
    from apps.events.models import EventRegistration

    from .models import NotificationPreference
    from .whatsapp import send_whatsapp

    context_base = _event_context(event)
    for registration in event.event_registrations.filter(
        state=EventRegistration.STATE_CONFIRMED
    ).select_related("user"):
        if not registration.user_id:
            continue
        prefs = NotificationPreference.for_user(registration.user)
        if prefs.email_reminders:
            body = render_to_string("notifications/emails/rsvp_reminder.txt", context_base)
            subject = f"[null Event] Reminder: {event.descriptive_name()}"
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [registration.user.email])
        if prefs.whatsapp_enabled:
            send_whatsapp(
                prefs.whatsapp_number,
                f"Reminder from null: {event.descriptive_name()} is tomorrow! "
                f"Details: {_event_url(event)}",
            )


@shared_task
def sync_event_to_google_calendar(event_id: int) -> None:
    """Ports Event#event_update_calendar. STUB: needs a Google service-account
    credential + GOOGLE_API_CALENDAR_ID, neither of which exist in this
    environment. Not wired to any trigger."""
    raise NotImplementedError("Google Calendar sync needs service-account credentials — not configured")


@shared_task
def post_to_twitter_via_ifttt(message: str) -> None:
    """Ports IftttMailer#twitter_status_update. STUB: needs an IFTTT Maker
    webhook key, which doesn't exist in this environment. Not wired to any
    trigger."""
    raise NotImplementedError("IFTTT/Twitter posting needs a webhook key — not configured")
