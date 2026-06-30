from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Event,
    EventRegistration,
    EventSession,
    EventSessionComment,
    EventType,
    Venue,
)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Mirrors app/admin/event.rb."""

    list_display = ["id", "chapter", "event_type", "name", "public", "start_time"]
    list_filter = ["public", "chapter", "venue", "event_type"]
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
class VenueAdmin(admin.ModelAdmin):
    list_display = ["id", "chapter", "name", "contact_name"]
    list_filter = ["chapter"]
    search_fields = ["name"]


@admin.register(EventType)
class EventTypeAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "public", "created_at"]
    list_filter = ["public"]
    search_fields = ["name"]


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    """Mirrors app/admin/event_session.rb — speaker assigned via autocomplete."""

    list_display = ["id", "name", "event", "user", "placeholder"]
    list_filter = ["placeholder"]
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
