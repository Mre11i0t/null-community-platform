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


class IncidentReport(models.Model):
    """Rev 3 trust & safety: confidential Code-of-Conduct incident
    reports, routed by email to the response team and tracked here.
    Deliberately minimal exposure: no public views, admin-only triage."""

    STATE_OPEN = "open"
    STATE_REVIEWING = "reviewing"
    STATE_RESOLVED = "resolved"
    STATE_CHOICES = [
        (STATE_OPEN, "Open"),
        (STATE_REVIEWING, "Reviewing"),
        (STATE_RESOLVED, "Resolved"),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    reporter = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="incident_reports"
    )
    description = models.TextField()
    where = models.CharField(max_length=255, blank=True, help_text="Event/venue/online space")
    contact_ok = models.BooleanField(default=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_OPEN)
    resolution_note = models.TextField(blank=True)

    class Meta:
        db_table = "incident_reports"

    def __str__(self):
        return f"Incident #{self.pk} ({self.state})"
