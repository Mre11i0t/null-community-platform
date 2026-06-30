from django.db import models

from apps.core.models import TimeStampedModel
from apps.events.models import Event


class EventMailerTask(TimeStampedModel):
    """Mirrors `event_mailer_tasks` — custom email blast to a filtered
    subset of an event's registrations. Delivery is meant to run via
    a Celery task (apps/notifications/tasks.py) once `ready_for_delivery`
    is set — see TODO there; execution is not yet wired up.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="mailer_tasks")
    subject = models.CharField(max_length=255)
    body = models.TextField()
    send_to_selected_only = models.BooleanField(default=False)
    ready_for_delivery = models.BooleanField(default=False)
    executed = models.BooleanField(default=False)
    status = models.CharField(max_length=255, blank=True)
    registration_state = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "event_mailer_tasks"

    def __str__(self):
        return self.subject


class EventAutomaticNotificationTask(TimeStampedModel):
    """Mirrors `event_automatic_notification_tasks` — the automatic
    notification modes (Announcement, Speaker Notification, Reminders,
    Admin OnCreate, Presentation Update). See doc/feature-document.md
    Part 7 for the full trigger table this implements.
    """

    MODE_ANNOUNCEMENT = "Announcement"
    MODE_SPEAKER_NOTIFICATION = "SpeakerNotification"
    MODE_EVENT_REMINDER = "EventReminder"
    MODE_SPEAKER_REMINDER = "SpeakerReminder"
    MODE_ADMIN_ON_CREATE = "AdminOnCreate"
    MODE_PRESENTATION_UPDATE_REMINDER = "PresentationUpdateReminder"

    MODE_CHOICES = [
        (MODE_ANNOUNCEMENT, "Announcement"),
        (MODE_SPEAKER_NOTIFICATION, "Speaker Notification"),
        (MODE_EVENT_REMINDER, "Event Reminder"),
        (MODE_SPEAKER_REMINDER, "Speaker Reminder"),
        (MODE_ADMIN_ON_CREATE, "Admin On Create"),
        (MODE_PRESENTATION_UPDATE_REMINDER, "Presentation Update Reminder"),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="automatic_notification_tasks")
    mode = models.CharField(max_length=255, choices=MODE_CHOICES)
    executed = models.BooleanField(default=False)

    class Meta:
        db_table = "event_automatic_notification_tasks"

    def __str__(self):
        return f"{self.event} - {self.mode}"
