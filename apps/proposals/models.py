from django.conf import settings
from django.db import models

from apps.chapters.models import Chapter
from apps.core.models import TimeStampedModel
from apps.events.models import EventType


class SessionProposal(TimeStampedModel):
    """Mirrors `session_proposals`. A member proposing a topic to a
    chapter for a future event. See app/models/session_proposal.rb —
    chapter leads are notified by email on creation (apps/proposals/signals.py).
    """

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="session_proposals")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_proposals")
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name="session_proposals")
    session_topic = models.CharField(max_length=255)
    session_description = models.TextField()

    class Meta:
        db_table = "session_proposals"

    def __str__(self):
        return self.session_topic


class SessionRequest(TimeStampedModel):
    """Mirrors `session_requests` — community-suggested topic for a chapter."""

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="session_requests")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_requests")
    session_topic = models.CharField(max_length=255)
    session_description = models.TextField()

    class Meta:
        db_table = "session_requests"

    def __str__(self):
        return self.session_topic


class UserAchievement(TimeStampedModel):
    """Mirrors `user_achievements`. See app/models/user_achievement.rb."""

    TYPE_VULNERABILITY_DISCOVERY = "Bug Discovery"
    TYPE_BUG_BOUNTY = "Bug Bounty"
    TYPE_OSS_PROJECT = "Open Source"
    TYPE_COMMUNITY_SUPPORT = "Community Support"

    TYPE_CHOICES = [
        (TYPE_VULNERABILITY_DISCOVERY, TYPE_VULNERABILITY_DISCOVERY),
        (TYPE_BUG_BOUNTY, TYPE_BUG_BOUNTY),
        (TYPE_OSS_PROJECT, TYPE_OSS_PROJECT),
        (TYPE_COMMUNITY_SUPPORT, TYPE_COMMUNITY_SUPPORT),
    ]

    SOURCE_SELF = "Self"
    SOURCE_NULL = "null"
    SOURCE_CHOICES = [(SOURCE_SELF, SOURCE_SELF), (SOURCE_NULL, SOURCE_NULL)]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements")
    source = models.CharField(max_length=255, choices=SOURCE_CHOICES, default=SOURCE_SELF)
    achievement_type = models.CharField(max_length=255, choices=TYPE_CHOICES)
    info = models.CharField(max_length=255)
    reference = models.CharField(max_length=255)

    class Meta:
        db_table = "user_achievements"
        constraints = [
            models.UniqueConstraint(fields=["user", "reference"], name="unique_reference_per_user"),
        ]

    def __str__(self):
        return f"{self.achievement_type}: {self.info}"
