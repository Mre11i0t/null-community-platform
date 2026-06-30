from django.contrib import admin

from .models import Page, PageAccessPermission


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Mirrors app/admin/page.rb."""

    list_display = ["id", "name", "title", "published"]
    list_filter = ["published"]
    search_fields = ["name", "title"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PageAccessPermission)
class PageAccessPermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "page", "user", "permission_type"]
    autocomplete_fields = ["page", "user"]
