from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.urls import reverse

from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Maps to the original `users` table (db/schema.rb).

    Devise fields (encrypted_password, confirmation_token, etc.) are
    replaced by Django's built-in auth + django-allauth equivalents;
    every *content* field from the original schema is preserved.
    """

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    handle = models.CharField(max_length=255, blank=True)

    twitter_handle = models.CharField(max_length=255, blank=True)
    facebook_profile = models.CharField(max_length=255, blank=True)
    linkedin_profile = models.CharField(max_length=255, blank=True)
    slideshare_profile = models.CharField(max_length=255, blank=True)
    github_profile = models.CharField(max_length=255, blank=True)

    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    homepage = models.URLField(max_length=255, blank=True)
    about_me = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.name or self.email

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name

    # --- ported from app/models/user.rb ---
    def has_twitter_handle(self):
        return bool(self.twitter_handle)

    def has_facebook_profile(self):
        return bool(self.facebook_profile)

    def has_github_profile(self):
        return bool(self.github_profile)

    def avatar_url(self):
        return self.avatar.url if self.avatar else "/static/images/default_image.png"

    def get_absolute_url(self):
        return reverse("accounts:public_profile", args=[self.pk])

    def registered_for_event(self, event):
        return self.event_registrations.filter(event=event).exists()

    def registration_for_event(self, event):
        return self.event_registrations.filter(event=event).first()

    def is_leader(self):
        return self.chapter_leads.filter(active=True).exists()

    def managed_chapters(self):
        from apps.chapters.models import Chapter

        chapter_ids = self.chapter_leads.filter(active=True).values_list("chapter_id", flat=True)
        return Chapter.objects.filter(id__in=chapter_ids)

    def managed_chapter(self, chapter):
        return self.chapter_leads.filter(chapter=chapter, active=True).exists()

    def managed_venues(self):
        from apps.events.models import Venue

        return Venue.objects.filter(chapter__in=self.managed_chapters())

    def managed_venue(self, venue):
        return venue is not None and venue.chapter_id in self.managed_chapters().values_list("id", flat=True)

    def managed_events(self):
        from django.utils import timezone

        from apps.events.models import Event

        return Event.objects.filter(chapter__in=self.managed_chapters(), end_time__gt=timezone.now())

    def managed_old_events(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.events.models import Event

        now = timezone.now()
        return Event.objects.filter(
            chapter__in=self.managed_chapters(),
            end_time__lt=now - timedelta(hours=8),
            start_time__gt=now - timedelta(days=30),
        )

    def speaker_sessions(self):
        return self.event_sessions.filter(placeholder=False).order_by("-created_at")

    def registered_participation(self):
        from django.db.models import Q

        from apps.events.models import EventRegistration

        return self.event_registrations.filter(
            Q(accepted=True) | Q(state=EventRegistration.STATE_CONFIRMED)
        ).order_by("-created_at")


class UserAuthProfile(TimeStampedModel):
    """OAuth identity, mirrors user_auth_profiles table."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_profiles")
    uid = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=255, blank=True)
    oauth_data = models.BinaryField(null=True, blank=True)
    extra = models.BinaryField(null=True, blank=True)

    class Meta:
        db_table = "user_auth_profiles"


class UserApiToken(TimeStampedModel):
    """Mirrors user_api_tokens — API auth, 24h expiry by default."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    user_agent = models.CharField(max_length=255, blank=True)
    client_name = models.CharField(max_length=255, blank=True)
    ip_address = models.CharField(max_length=255, blank=True)
    token = models.CharField(max_length=255, unique=True, db_index=True)
    active = models.BooleanField(default=False, db_index=True)
    expire_at = models.DateTimeField(db_index=True, null=True, blank=True)

    class Meta:
        db_table = "user_api_tokens"
