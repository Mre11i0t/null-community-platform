from django.db import models


class PageVisit(models.Model):
    """Rev 3 built-in traffic attribution — answers "which chapter site
    gets the hits and where do visitors come from" without a third-party
    tracker. Cookieless and PII-free by construction: no user id, no IP,
    no fingerprint — just host, path, and where the visitor came from.
    That keeps it out of DPDP/GDPR consent territory entirely.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    host = models.CharField(max_length=255, db_index=True)
    path = models.CharField(max_length=255)
    chapter = models.ForeignKey(
        "chapters.Chapter", null=True, blank=True, on_delete=models.SET_NULL, related_name="page_visits"
    )
    referrer_domain = models.CharField(max_length=255, blank=True, db_index=True)
    utm_source = models.CharField(max_length=64, blank=True)
    utm_medium = models.CharField(max_length=64, blank=True)
    utm_campaign = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "page_visits"

    def __str__(self):
        return f"{self.host}{self.path}"
