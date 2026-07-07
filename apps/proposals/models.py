from django.conf import settings
from django.db import models

from apps.chapters.models import Chapter
from apps.core.models import TimeStampedModel
from apps.events.models import EventType


class SessionProposal(TimeStampedModel):
    """Mirrors `session_proposals`. A member proposing a topic to a
    chapter for a future event. See app/models/session_proposal.rb —
    chapter leads are notified by email on creation (apps/proposals/signals.py).

    Rev 3 (closes gap #6): proposals now carry a review pipeline —
    submitted → under review → accepted / rejected / waitlisted →
    scheduled — and every transition emails the proposer, which the
    original never did (members submitted into a void).
    """

    STATUS_SUBMITTED = "submitted"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_WAITLISTED = "waitlisted"
    STATUS_SCHEDULED = "scheduled"

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_UNDER_REVIEW, "Under review"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_WAITLISTED, "Waitlisted"),
        (STATUS_SCHEDULED, "Scheduled"),
    ]

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="session_proposals")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_proposals")
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name="session_proposals")
    session_topic = models.CharField(max_length=255)
    session_description = models.TextField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)

    class Meta:
        db_table = "session_proposals"

    def __str__(self):
        return self.session_topic

    def average_score(self):
        from django.db.models import Avg

        return self.reviews.aggregate(avg=Avg("score"))["avg"]

    def set_status(self, new_status, note=""):
        """Transitions the pipeline and emails the proposer — the whole
        point of gap #6 was that submitters never heard back."""
        from django.core.mail import send_mail

        valid = dict(self.STATUS_CHOICES)
        if new_status not in valid:
            raise ValueError("Invalid status")
        if new_status == self.status:
            return
        self.status = new_status
        self.save(update_fields=["status", "updated_at"])

        body = (
            f'Your session proposal "{self.session_topic}" for null {self.chapter.name} '
            f"is now: {valid[new_status]}."
        )
        if note:
            body += f"\n\nNote from the reviewers: {note}"
        body += f"\n\nView your proposals: {settings.SITE_BASE_URL}/session_proposals/"
        send_mail(
            subject=f"[null] Proposal update — {valid[new_status]}: {self.session_topic}",
            message=body,
            from_email=None,
            recipient_list=[self.user.email],
            fail_silently=True,
        )


class ProposalReview(TimeStampedModel):
    """Rev 3 CFP reviewing: one score+comment per reviewer per proposal."""

    proposal = models.ForeignKey(SessionProposal, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="proposal_reviews"
    )
    score = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "proposal_reviews"
        constraints = [
            models.UniqueConstraint(fields=["proposal", "reviewer"], name="one_review_per_reviewer"),
        ]

    def __str__(self):
        return f"{self.reviewer} on {self.proposal}: {self.score}"


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
