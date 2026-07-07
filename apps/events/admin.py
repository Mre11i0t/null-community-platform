from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Event,
    EventRegistration,
    EventSession,
    EventSessionComment,
    EventType,
    Venue,
)


class SoftDeleteAdminMixin:
    """Admin sees everything (default manager), with archive/restore
    bulk actions and an Archived column — the recovery path for what
    leads soft-delete."""

    actions = ["archive_selected", "restore_selected"]

    @admin.display(boolean=True, description="Archived")
    def is_archived(self, obj):
        return obj.deleted_at is not None

    @admin.action(description="Archive selected (soft delete)")
    def archive_selected(self, request, queryset):
        queryset.filter(deleted_at__isnull=True).update(deleted_at=timezone.now())

    @admin.action(description="Restore selected")
    def restore_selected(self, request, queryset):
        queryset.update(deleted_at=None)


@admin.register(Event)
class EventAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    """Mirrors app/admin/event.rb."""

    list_display = ["id", "chapter", "event_type", "name", "public", "start_time", "is_archived"]
    list_filter = ["public", "chapter", "venue", "event_type", ("deleted_at", admin.EmptyFieldListFilter)]
    search_fields = ["name"]
    date_hierarchy = "start_time"
    autocomplete_fields = ["chapter", "venue", "event_type"]

    fieldsets = (
        (
            "Basic Details",
            {
                "fields": (
                    "event_type",
                    "chapter",
                    "venue",
                    "name",
                    "description",
                    "can_show_on_homepage",
                    "can_show_on_archive",
                    "accepting_registration",
                    "start_time",
                    "end_time",
                )
            },
        ),
        (
            "Publishing",
            {
                "description": "Setting <strong>public</strong> publishes the event and triggers "
                "scheduled tasks: announcement, speaker notification, calendar update.",
                "fields": ("public",),
            },
        ),
        (
            "Registration",
            {
                "fields": (
                    "registration_start_time",
                    "registration_end_time",
                    "registration_instructions",
                    "max_registration",
                )
            },
        ),
        ("Media", {"fields": ("image",)}),
        (
            "Notifications",
            {
                "fields": (
                    "notification_state",
                    "ready_for_announcement",
                    "ready_for_notifications",
                    "ready_for_reminders",
                )
            },
        ),
    )

    @admin.display(description="View on site")
    def view_link(self, obj):
        return format_html('<a href="{}" target="_blank">View Event</a>', obj.get_absolute_url())


@admin.register(Venue)
class VenueAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    list_display = ["id", "chapter", "name", "contact_name", "is_archived"]
    list_filter = ["chapter", ("deleted_at", admin.EmptyFieldListFilter)]
    search_fields = ["name"]


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "public", "created_at"]
    list_filter = ["public"]
    search_fields = ["name"]


@admin.register(EventSession)
class EventSessionAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    """Mirrors app/admin/event_session.rb — speaker assigned via autocomplete."""

    list_display = ["id", "name", "event", "user", "placeholder", "is_archived"]
    list_filter = ["placeholder", ("deleted_at", admin.EmptyFieldListFilter)]
    search_fields = ["name"]
    autocomplete_fields = ["event", "user"]


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    """Mirrors app/admin/event_registration.rb — batch state transitions,
    100 per page, read-only edit form (state changes only via batch actions)."""

    list_per_page = 100
    list_display = ["id", "event", "user", "state", "created_at"]
    list_filter = ["state", "event"]
    autocomplete_fields = ["event", "user"]
    actions = ["mark_provisional", "mark_confirmed", "mark_not_attending", "mark_absent"]

    def _batch_set_state(self, request, queryset, state):
        for registration in queryset:
            registration.set_state(state)

    @admin.action(description="Set state: Provisional")
    def mark_provisional(self, request, queryset):
        self._batch_set_state(request, queryset, EventRegistration.STATE_PROVISIONAL)

    @admin.action(description="Set state: Confirmed")
    def mark_confirmed(self, request, queryset):
        self._batch_set_state(request, queryset, EventRegistration.STATE_CONFIRMED)

    @admin.action(description="Set state: Not Attending")
    def mark_not_attending(self, request, queryset):
        self._batch_set_state(request, queryset, EventRegistration.STATE_NOT_ATTENDING)

    @admin.action(description="Set state: Absent")
    def mark_absent(self, request, queryset):
        self._batch_set_state(request, queryset, EventRegistration.STATE_ABSENT)


@admin.register(EventSessionComment)
class EventSessionCommentAdmin(admin.ModelAdmin):
    list_display = ["id", "event_session", "user", "created_at"]
