from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.events.models import Event

from .models import EventAutomaticNotificationTask
from .tasks import send_automatic_notification


@receiver(post_save, sender=Event)
def notify_admin_on_create(sender, instance, created, **kwargs):
    """Ports Event's `after_create :notify_admin_on_create` — fires on every
    event creation regardless of public status (admins/leads are notified a
    new event was created; publishing it is a separate manual step)."""
    if not created:
        return
    task = EventAutomaticNotificationTask.objects.create(
        event=instance, mode=EventAutomaticNotificationTask.MODE_ADMIN_ON_CREATE
    )
    send_automatic_notification.delay(task.pk)
