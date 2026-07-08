import datetime

import pytest
from django.conf import settings
from django.core import mail
from django.urls import reverse
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

    # Finished: once the presentation-upload window (~7 days) has elapsed,
    # the machine reaches its terminal state. Previously it stalled forever
    # at PresentationUpdate and never reached Finished (defined but unused).
    event.end_time = now - datetime.timedelta(days=8)
    event.save(update_fields=["end_time"])
    dispatch_event_notifications()
    event.refresh_from_db()
    assert event.notification_state == Event.STATE_FINISHED


def test_dispatch_is_idempotent_once_state_has_advanced():
    event = EventFactory(public=True, ready_for_notifications=True, notification_state=Event.STATE_INIT)

    dispatch_event_notifications()
    first_task_count = EventAutomaticNotificationTask.objects.filter(event=event).count()

    dispatch_event_notifications()
    second_task_count = EventAutomaticNotificationTask.objects.filter(event=event).count()

    assert first_task_count == second_task_count


# --- Rev 3 communications ------------------------------------------------------


def test_rsvp_reminder_honors_email_preference():
    import datetime as dt

    from django.core import mail
    from django.utils import timezone

    from apps.events.models import EventRegistration
    from apps.notifications.models import NotificationPreference
    from apps.notifications.tasks import _send_rsvp_reminders
    from tests.factories import EventFactory, EventRegistrationFactory

    event = EventFactory(
        public=True,
        start_time=timezone.now() + dt.timedelta(days=1),
        end_time=timezone.now() + dt.timedelta(days=1, hours=2),
    )
    wants = EventRegistrationFactory(event=event)
    wants.set_state(EventRegistration.STATE_CONFIRMED)
    opted_out = EventRegistrationFactory(event=event)
    opted_out.set_state(EventRegistration.STATE_CONFIRMED)
    prefs = NotificationPreference.for_user(opted_out.user)
    prefs.email_reminders = False
    prefs.save()

    mail.outbox.clear()
    _send_rsvp_reminders(event)

    recipients = [addr for m in mail.outbox for addr in m.to]
    assert wants.user.email in recipients
    assert opted_out.user.email not in recipients


def test_feedback_request_sweep_and_submission(client):
    import datetime as dt

    from django.core import mail
    from django.urls import reverse
    from django.utils import timezone

    from apps.events.models import EventFeedback, EventRegistration
    from apps.events.tasks import send_feedback_requests
    from tests.factories import EventFactory, EventRegistrationFactory

    event = EventFactory(
        public=True,
        start_time=timezone.now() - dt.timedelta(hours=10),
        end_time=timezone.now() - dt.timedelta(hours=8),
    )
    registration = EventRegistrationFactory(event=event)
    registration.set_state(EventRegistration.STATE_CONFIRMED)

    mail.outbox.clear()
    assert send_feedback_requests() == 1
    assert send_feedback_requests() == 0  # idempotent
    assert any("How was" in m.subject for m in mail.outbox)

    client.force_login(registration.user)
    response = client.post(
        reverse("events:event_feedback", args=[event.pk]),
        {"rating": "4", "comment": "Solid lineup"},
    )
    assert response.status_code == 302
    feedback = EventFeedback.objects.get(event=event, user=registration.user)
    assert feedback.rating == 4
    assert event.average_feedback_rating() == 4

    # non-attendee 404s
    from tests.factories import UserFactory

    client.force_login(UserFactory())
    assert client.get(reverse("events:event_feedback", args=[event.pk])).status_code == 404


def test_preference_center_updates(client):
    from django.urls import reverse

    from apps.notifications.models import NotificationPreference
    from tests.factories import UserFactory

    user = UserFactory()
    client.force_login(user)
    response = client.post(
        reverse("accounts:notification_preferences"),
        {"email_reminders": "", "email_speaker_notifications": "on",
         "email_feedback_requests": "on", "whatsapp_enabled": "on",
         "whatsapp_number": "+919812345678"},
    )
    assert response.status_code == 200
    prefs = NotificationPreference.objects.get(user=user)
    assert not prefs.email_reminders
    assert prefs.whatsapp_enabled and prefs.whatsapp_number == "+919812345678"


def test_whatsapp_dry_run_without_credentials():
    from apps.notifications.whatsapp import send_whatsapp

    assert send_whatsapp("+919812345678", "hello") is False  # not configured -> logged, not sent


def test_mailer_test_send_goes_only_to_the_lead(client):
    from django.core import mail
    from django.urls import reverse

    from tests.factories import ChapterLeadFactory, EventFactory, EventMailerTaskFactory

    event = EventFactory()
    task = EventMailerTaskFactory(event=event, subject="Big news", body="**hello**")
    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)

    mail.outbox.clear()
    client.post(reverse("leads:mailer_task_test_send", args=[event.pk, task.pk]))

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [lead.user.email]
    assert mail.outbox[0].subject.startswith("[TEST]")


# --- Rev 3 webhooks ------------------------------------------------------------


def _mock_post(monkeypatch, status=200):
    calls = []

    class FakeResponse:
        status_code = status
        text = "ok"

    def fake_post(url, data=None, headers=None, timeout=None):
        calls.append({"url": url, "data": data, "headers": headers})
        return FakeResponse()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def test_event_publish_fires_signed_webhook(monkeypatch):
    import datetime as dt
    import hashlib
    import hmac

    from django.utils import timezone

    from apps.notifications.models import WebhookDelivery, WebhookEndpoint
    from tests.factories import EventFactory

    calls = _mock_post(monkeypatch)
    event = EventFactory(
        public=False,
        start_time=timezone.now() + dt.timedelta(days=3),
        end_time=timezone.now() + dt.timedelta(days=3, hours=2),
    )
    endpoint = WebhookEndpoint.objects.create(chapter=event.chapter, url="https://example.com/hook")
    assert calls == []  # not public yet

    event.public = True
    event.save()

    assert len(calls) == 1
    body = calls[0]["data"]
    expected = hmac.new(endpoint.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    assert calls[0]["headers"]["X-Null-Signature"] == f"sha256={expected}"
    assert calls[0]["headers"]["X-Null-Event"] == "event.published"

    delivery = WebhookDelivery.objects.get()
    assert delivery.kind == "event.published" and delivery.delivered_at is not None

    # saving again without a publish flip fires nothing new
    event.name = "renamed"
    event.save()
    assert len(calls) == 1


def test_registration_webhooks_created_and_checked_in(monkeypatch):
    import datetime as dt

    from django.utils import timezone

    from apps.notifications.models import WebhookEndpoint
    from tests.factories import EventFactory, EventRegistrationFactory

    calls = _mock_post(monkeypatch)
    event = EventFactory(
        public=True,
        check_in_enabled=True,
        start_time=timezone.now() + dt.timedelta(hours=1),
        end_time=timezone.now() + dt.timedelta(hours=4),
    )
    WebhookEndpoint.objects.create(chapter=event.chapter, url="https://example.com/hook")
    calls.clear()  # drop the event.published call

    registration = EventRegistrationFactory(event=event)
    kinds = [c["headers"]["X-Null-Event"] for c in calls]
    assert "registration.created" in kinds

    registration.check_in()
    kinds = [c["headers"]["X-Null-Event"] for c in calls]
    assert "registration.checked_in" in kinds


def test_webhook_lead_ui_add_and_remove(client):
    from apps.notifications.models import WebhookEndpoint
    from tests.factories import ChapterLeadFactory

    lead = ChapterLeadFactory()
    client.force_login(lead.user)

    client.post(
        reverse("leads:webhook_index"),
        {"chapter": lead.chapter.pk, "url": "https://hooks.example.com/x"},
    )
    endpoint = WebhookEndpoint.objects.get()
    assert endpoint.chapter == lead.chapter and len(endpoint.secret) == 64

    # http:// rejected
    client.post(reverse("leads:webhook_index"), {"chapter": lead.chapter.pk, "url": "http://x.com"})
    assert WebhookEndpoint.objects.count() == 1

    # another chapter's lead can't delete it
    outsider = ChapterLeadFactory()
    client.force_login(outsider.user)
    assert client.post(reverse("leads:webhook_delete", args=[endpoint.pk])).status_code == 403

    client.force_login(lead.user)
    client.post(reverse("leads:webhook_delete", args=[endpoint.pk]))
    assert WebhookEndpoint.objects.count() == 0


# --- Rev 3 integrations modernization -------------------------------------------


def test_broadcast_skips_unconfigured_channels():
    from apps.notifications.broadcast import broadcast

    assert broadcast("hello world") == []  # nothing configured -> nothing sent


def test_broadcast_sends_to_configured_discord(settings, monkeypatch):
    import requests

    settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/x"
    calls = []

    monkeypatch.setattr(
        requests, "post", lambda url, json=None, timeout=None: calls.append((url, json))
    )

    from apps.notifications.broadcast import broadcast

    assert broadcast("event time!") == ["discord"]
    assert calls[0][0] == settings.DISCORD_WEBHOOK_URL
    assert calls[0][1]["content"] == "event time!"


def test_announcement_task_fans_out_to_broadcast(settings, monkeypatch):
    import datetime as dt

    import requests
    from django.utils import timezone

    from apps.notifications.tasks import _send_announcement
    from tests.factories import EventFactory

    settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/x"
    calls = []
    monkeypatch.setattr(
        requests, "post", lambda url, json=None, timeout=None, **kw: calls.append((url, json))
    )

    event = EventFactory(
        public=True,
        start_time=timezone.now() + dt.timedelta(days=7),
        end_time=timezone.now() + dt.timedelta(days=7, hours=2),
    )
    _send_announcement(event)

    assert any("hooks.slack.com" in url for url, _ in calls)


def test_leads_can_create_event_types_and_see_notification_log(client):
    from apps.events.models import EventType
    from tests.factories import ChapterLeadFactory

    lead = ChapterLeadFactory()
    client.force_login(lead.user)

    client.post(
        reverse("leads:event_type_index"),
        {"name": "Hardware Village", "public": "on", "registration_required": "on"},
    )
    assert EventType.objects.filter(name="Hardware Village").exists()

    # duplicate rejected
    client.post(reverse("leads:event_type_index"), {"name": "hardware village"})
    assert EventType.objects.filter(name__iexact="hardware village").count() == 1

    assert client.get(reverse("leads:notification_log")).status_code == 200
