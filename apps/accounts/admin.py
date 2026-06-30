from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, UserApiToken, UserAuthProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Mirrors the ActiveAdmin User resource: list shows id/name/email/
    confirmation status/sign-in info; batch confirm; full profile on edit."""

    ordering = ["-created_at"]
    list_display = ["id", "email", "name", "is_active", "is_staff", "last_login"]
    list_filter = ["is_active", "is_staff"]
    search_fields = ["email", "name", "handle"]
    readonly_fields = ["created_at", "updated_at", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name", "handle", "avatar", "homepage", "about_me")}),
        (
            "Social",
            {
                "fields": (
                    "twitter_handle",
                    "facebook_profile",
                    "linkedin_profile",
                    "slideshare_profile",
                    "github_profile",
                )
            },
        ),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions")

    actions = ["confirm_users"]

    @admin.action(description="Mark selected users as active")
    def confirm_users(self, request, queryset):
        queryset.update(is_active=True)


@admin.register(UserApiToken)
class UserApiTokenAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "client_name", "active", "expire_at"]
    list_filter = ["active"]
    readonly_fields = ["token", "created_at", "updated_at"]


@admin.register(UserAuthProfile)
class UserAuthProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "provider", "uid"]
