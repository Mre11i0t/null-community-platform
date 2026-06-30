from django.contrib import admin

from .models import EventAutomaticNotificationTask, EventMailerTask


@admin.register(EventMailerTask)
class EventMailerTaskAdmin(admin.ModelAdmin):
    """Mirrors app/admin/event_mailer_task.rb."""

    list_display = ["id", "event", "subject", "registration_state", "ready_for_delivery", "executed"]
    list_filter = ["ready_for_delivery", "executed"]
    autocomplete_fields = ["event"]


@admin.register(EventAutomaticNotificationTask)
class EventAutomaticNotificationTaskAdmin(admin.ModelAdmin):
    """Mirrors app/admin/event_automatic_notification_task.rb."""

    list_display = ["id", "event", "mode", "executed"]
    list_filter = ["mode", "executed"]
    autocomplete_fields = ["event"]
