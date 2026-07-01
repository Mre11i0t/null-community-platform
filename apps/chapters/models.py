from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Chapter(TimeStampedModel):
    """Mirrors the `chapters` table. See app/models/chapter.rb."""

    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    city = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)
    chapter_email = models.EmailField(max_length=255, blank=True)
    image = models.ImageField(upload_to="chapters/", blank=True, null=True)
    twitter_handle = models.CharField(max_length=255, blank=True)
    facebook_profile = models.CharField(max_length=255, blank=True)
    linkedin_profile = models.CharField(max_length=255, blank=True)
    slideshare_profile = models.CharField(max_length=255, blank=True)
    github_profile = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "chapters"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("chapters:detail", args=[self.pk])

    # --- ported from chapter.rb ---
    def has_twitter_handle(self):
        return bool(self.twitter_handle)

    def has_facebook_profile(self):
        return bool(self.facebook_profile)

    def has_github_profile(self):
        return bool(self.github_profile)

    def image_url(self):
        return self.image.url if self.image else "/static/images/default_image.png"

    def leads(self):
        from apps.accounts.models import User

        user_ids = self.chapter_leads.filter(active=True).values_list("user_id", flat=True)
        return User.objects.filter(id__in=user_ids)

    def past_events(self):
        from apps.events.models import Event

        return Event.objects.archives().filter(chapter=self)

    def upcoming_events(self):
        from apps.events.models import Event

        return Event.objects.future_public_events().filter(chapter=self)

    def next_upcoming_event(self):
        return self.upcoming_events().order_by("start_time").first()

    def upcoming_events_ics(self):
        """Ports Chapter#upcoming_events_ics — used by the /chapters/<id>/calendar.ics feed."""
        from icalendar import Calendar

        cal = Calendar()
        cal.add("x-wr-calname", f"null {self.name} Events")
        cal.add("version", "2.0")
        cal.add("prodid", "-//null Community Platform//null.community//")
        for event in self.upcoming_events().order_by("start_time"):
            cal.add_component(event.to_ics_event())
        return cal.to_ical()

    @classmethod
    def active_chapters(cls):
        return cls.objects.filter(active=True)


class ChapterLead(TimeStampedModel):
    """Mirrors chapter_leads — join table assigning a user as a chapter leader."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chapter_leads")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="chapter_leads")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "chapter_leads"
        constraints = [
            models.UniqueConstraint(fields=["user", "chapter"], name="unique_user_per_chapter"),
        ]

    def __str__(self):
        return f"{self.user} @ {self.chapter}"
