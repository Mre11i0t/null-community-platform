from django.contrib import admin

from .models import IncidentReport


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    """Confidential triage — visible to admins only, never public."""

    list_display = ["id", "state", "where", "contact_ok", "created_at"]
    list_filter = ["state"]
    readonly_fields = ["reporter", "description", "where", "contact_ok", "created_at"]
