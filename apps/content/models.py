from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Page(TimeStampedModel):
    """Mirrors `pages`. See app/models/page.rb. Dynamic CMS-style content
    page (e.g. Code of Conduct, Privacy Policy, How to start a Chapter)."""

    name = models.CharField(max_length=255)
    description = models.TextField()
    navigation_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, unique=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    published = models.BooleanField(default=False)

    class Meta:
        db_table = "pages"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            # ported from Page#slugify! — "#{name} #{id}".parameterize
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.slug == slugify(self.name):
            # original Rails app appends the id after first save to guarantee uniqueness
            self.slug = slugify(f"{self.name} {self.pk}")
            super().save(update_fields=["slug"])

    def get_absolute_url(self):
        return reverse("content:page_detail", args=[self.slug])

    @classmethod
    def published_pages(cls):
        return cls.objects.filter(published=True)


class PageAccessPermission(TimeStampedModel):
    """Mirrors `page_access_permissions` — per-user ReadWrite/ReadOnly grants."""

    READ_WRITE = "ReadWrite"
    READ_ONLY = "ReadOnly"
    PERMISSION_CHOICES = [(READ_WRITE, READ_WRITE), (READ_ONLY, READ_ONLY)]

    permission_type = models.CharField(max_length=255, choices=PERMISSION_CHOICES)
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="access_permissions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="page_permissions")

    class Meta:
        db_table = "page_access_permissions"
