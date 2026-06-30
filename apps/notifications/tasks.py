"""Celery tasks replacing the original Resque jobs + Resque Scheduler.

STATUS: scaffolded, not yet implemented. The original Rails app's
EventNotification state machine (app/models/event_notification.rb) and
EventMailerTask#execute are the source of truth for the logic that
belongs in each task below.

TODO:
- send_event_mailer_task(task_id): render EventMailerTask.body as
  markdown and email every registration matching registration_state.
- send_automatic_notification(task_id): dispatch on
  EventAutomaticNotificationTask.mode (see MODE_CHOICES).
- schedule_event_reminders(event_id): replace
  Event#setup_scheduled_tasks — schedule reminder1 (T-2d), reminder2
  (T-1d), and presentation-update-reminder (T+1h after end) via
  celery beat / apply_async(eta=...).
- sync_event_to_google_calendar(event_id): port Event#event_update_calendar.
- post_to_twitter_via_ifttt(message): port IftttMailer#twitter_status_update.
"""

from celery import shared_task


@shared_task
def send_event_mailer_task(task_id: int) -> None:
    raise NotImplementedError("Port EventMailerTask#execute from the original Rails app")


@shared_task
def send_automatic_notification(task_id: int) -> None:
    raise NotImplementedError("Port EventAutomaticNotificationTask execution logic")
