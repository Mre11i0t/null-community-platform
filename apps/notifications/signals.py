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


def _event_payload(event):
    return {
        "id": event.pk,
        "name": event.name,
        "chapter": event.chapter.name,
        "start_time": event.start_time.isoformat(),
        "url": f"{event.chapter.site_url()}{event.get_absolute_url()}",
    }


from django.db.models.signals import pre_save


@receiver(pre_save, sender=Event)
def _cache_previous_public(sender, instance, **kwargs):
    if instance.pk:
        previous = Event.objects.filter(pk=instance.pk).values_list("public", flat=True).first()
        instance._was_public = bool(previous)
    else:
        instance._was_public = False


@receiver(post_save, sender=Event)
def webhook_on_publish(sender, instance, created, **kwargs):
    """Rev 3 webhooks: fire event.published the first time an event
    flips public (or is created already-public)."""
    from .webhooks import emit

    if instance.public and not getattr(instance, "_was_public", False):
        emit(instance.chapter, "event.published", _event_payload(instance))


def _registration_payload(registration):
    return {
        "event_id": registration.event_id,
        "event": registration.event.name,
        "state": registration.state,
        "registration_id": registration.pk,
    }


def connect_registration_webhooks():
    from django.db.models.signals import post_save as ps

    from apps.events.models import EventRegistration

    def on_registration(sender, instance, created, **kwargs):
        from .webhooks import emit

        if created:
            emit(instance.event.chapter, "registration.created", _registration_payload(instance))
        elif instance.checked_in_at and not getattr(instance, "_webhook_checkin_sent", False):
            instance._webhook_checkin_sent = True
            emit(instance.event.chapter, "registration.checked_in", _registration_payload(instance))

    ps.connect(on_registration, sender=EventRegistration, weak=False, dispatch_uid="registration-webhooks")


connect_registration_webhooks()
