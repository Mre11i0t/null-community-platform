from django.contrib import admin

from .models import Chapter, ChapterLead


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    """Mirrors app/admin/chapter.rb."""

    list_display = ["id", "code", "name", "city", "country", "active"]
    list_filter = ["active"]
    search_fields = ["name", "code"]


@admin.register(ChapterLead)
class ChapterLeadAdmin(admin.ModelAdmin):
    list_display = ["id", "chapter", "user", "active"]
    list_filter = ["chapter", "active"]
    autocomplete_fields = ["user"]
