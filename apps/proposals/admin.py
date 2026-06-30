from django.contrib import admin

from .models import SessionProposal, SessionRequest, UserAchievement


@admin.register(SessionProposal)
class SessionProposalAdmin(admin.ModelAdmin):
    list_display = ["id", "chapter", "user", "event_type", "session_topic", "created_at"]
    list_filter = ["chapter", "event_type"]
    autocomplete_fields = ["chapter", "user", "event_type"]


@admin.register(SessionRequest)
class SessionRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "chapter", "user", "session_topic", "created_at"]
    list_filter = ["chapter"]
    autocomplete_fields = ["chapter", "user"]


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "achievement_type", "source", "info"]
    list_filter = ["achievement_type", "source"]
    autocomplete_fields = ["user"]
