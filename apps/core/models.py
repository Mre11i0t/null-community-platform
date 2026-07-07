from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """created_at / updated_at on every original Rails table."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteModel(models.Model):
    """Archive-instead-of-delete (closes original gap #2: the Rails app
    disabled destroy actions with no alternative). The default manager
    still returns everything — admin needs to see archived rows — so
    public-facing querysets/views must go through `.alive()`."""

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
