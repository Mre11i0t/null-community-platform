"""Rev 3 parity with the Audited gem: the original logged every change
to every record. django-auditlog's middleware was already installed but
no models were registered, so nothing was actually being audited —
this closes that silently-missing piece. Log entries appear in the
admin under Audit log."""

from auditlog.registry import auditlog


def register_audited_models():
    from apps.accounts.models import User
    from apps.chapters.models import Chapter, ChapterLead
    from apps.content.models import Page, PageAccessPermission
    from apps.events.models import (
        Event,
        EventRegistration,
        EventSession,
        EventType,
        Venue,
    )
    from apps.notifications.models import EventMailerTask, WebhookEndpoint
    from apps.proposals.models import SessionProposal

    auditlog.register(User, exclude_fields=["password", "last_login"])
    for model in (
        Chapter,
        ChapterLead,
        Venue,
        EventType,
        Event,
        EventSession,
        EventRegistration,
        Page,
        PageAccessPermission,
        SessionProposal,
        EventMailerTask,
        WebhookEndpoint,
    ):
        auditlog.register(model)
