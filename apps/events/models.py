from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.chapters.models import Chapter
from apps.core.models import SoftDeleteModel, SoftDeleteQuerySet, TimeStampedModel
from taggit.managers import TaggableManager


class Venue(TimeStampedModel, SoftDeleteModel):
    """Mirrors `venues`. See app/models/venue.rb."""

    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="venues")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    address = models.TextField()
    map_url = models.URLField(max_length=255, blank=True)
    map_embedd_code = models.TextField(blank=True)
    contact_name = models.CharField(max_length=255)
    contact_email = models.EmailField(max_length=255, blank=True)
    contact_mobile = models.CharField(max_length=255, blank=True)
    contact_notes = models.TextField(blank=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        db_table = "venues"

    def __str__(self):
        return self.name


class EventType(TimeStampedModel):
    """Mirrors `event_types`. See app/models/event_type.rb."""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    max_participant = models.IntegerField(default=10000)
    public = models.BooleanField(null=True, blank=True)
    registration_required = models.BooleanField(default=False)
    invitation_required = models.BooleanField(default=False)

    class Meta:
        db_table = "event_types"

    def __str__(self):
        return self.name


class EventQuerySet(SoftDeleteQuerySet):
    """Ported from the scopes in app/models/event.rb. All public-facing
    scopes exclude soft-deleted events."""

    def future_events(self):
        return self.alive().filter(end_time__gt=timezone.now())

    def future_public_events(self):
        return self.future_events().filter(public=True)

    def public_events(self):
        return self.alive().filter(public=True)

    def archives(self):
        return self.alive().filter(
            public=True, can_show_on_archive=True, start_time__lt=timezone.now()
        )


class Event(TimeStampedModel, SoftDeleteModel):
    """Mirrors `events`. See app/models/event.rb.

    Notification state machine values mirror EventNotification's
    STATE_* constants (Init -> InitialNotifications -> Reminder1 ->
    Reminder2 -> PresentationUpdate -> Finished), driven by Celery
    tasks instead of Resque Scheduler. See apps/notifications.
    """

    STATE_INIT = "Init"
    STATE_INITIAL_NOTIFICATIONS = "InitialNotifications"
    STATE_REMINDER1 = "Reminder1"
    STATE_REMINDER2 = "Reminder2"
    STATE_PRESENTATION_UPDATE = "PresentationUpdate"
    STATE_FINISHED = "Finished"

    NOTIFICATION_STATE_CHOICES = [
        (STATE_INIT, "Init"),
        (STATE_INITIAL_NOTIFICATIONS, "Initial Notifications"),
        (STATE_REMINDER1, "Reminder 1"),
        (STATE_REMINDER2, "Reminder 2"),
        (STATE_PRESENTATION_UPDATE, "Presentation Update"),
        (STATE_FINISHED, "Finished"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.PROTECT, related_name="events")
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    event_type = models.ForeignKey(EventType, on_delete=models.PROTECT, related_name="events")

    public = models.BooleanField(null=True, blank=True)
    can_show_on_homepage = models.BooleanField(default=True)
    can_show_on_archive = models.BooleanField(default=True)
    accepting_registration = models.BooleanField(default=True)

    state = models.CharField(max_length=255, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    registration_start_time = models.DateTimeField(null=True, blank=True)
    registration_end_time = models.DateTimeField(null=True, blank=True)
    registration_instructions = models.TextField(blank=True)

    slug = models.SlugField(max_length=255, blank=True, db_index=True)

    ready_for_announcement = models.BooleanField(default=False)
    announced_at = models.DateTimeField(null=True, blank=True)
    ready_for_notifications = models.BooleanField(default=False)
    notifications_sent_at = models.DateTimeField(null=True, blank=True)
    ready_for_reminders = models.BooleanField(null=True, blank=True)

    calendar_event_id = models.CharField(max_length=255, blank=True)
    notification_state = models.CharField(
        max_length=255, choices=NOTIFICATION_STATE_CHOICES, default=STATE_INIT, blank=True
    )
    max_registration = models.IntegerField(default=0)
    image = models.ImageField(upload_to="events/", blank=True, null=True)

    # Rev 3 check-in — both flags per-event, independent, default OFF.
    # check_in_enabled surfaces QR codes/scanner/kiosk/dashboard;
    # auto_absent_enabled lets the post-event sweep mark no-shows Absent.
    check_in_enabled = models.BooleanField(default=False)
    auto_absent_enabled = models.BooleanField(default=False)
    auto_absent_processed_at = models.DateTimeField(null=True, blank=True)

    # Rev 3 registration upgrades: leader-defined extra RSVP questions
    # (list of {"label": str, "required": bool}) and how many hours
    # before start_time a cancellation stops being free — cancelling
    # inside the window counts as a no-show (Absent). 0 = cancel anytime.
    custom_questions = models.JSONField(default=list, blank=True)
    cancellation_deadline_hours = models.PositiveIntegerField(default=0, blank=True)

    # Rev 3 communications: set once the post-event feedback request
    # email has gone out (idempotency for the beat sweep).
    feedback_requested_at = models.DateTimeField(null=True, blank=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        db_table = "events"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.pk])

    # --- ported from event.rb ---
    def descriptive_name(self):
        return " ".join(
            [
                "null",
                self.chapter.name,
                self.event_type.name,
                self.start_time.strftime("%d %B %Y"),
                self.name,
            ]
        )

    def invite_only(self):
        return self.event_type.invitation_required

    def has_registration_instructions(self):
        return bool(self.registration_instructions)

    def active_registration_count(self):
        """Seats actually consumed: Provisional + Confirmed. Waitlisted,
        Not Attending, and Absent registrations don't hold a seat (the
        original counted every row, which let cancellations permanently
        eat capacity)."""
        return self.event_registrations.filter(
            state__in=[EventRegistration.STATE_PROVISIONAL, EventRegistration.STATE_CONFIRMED]
        ).count()

    def registration_allowed(self):
        if self.max_registration and self.max_registration > 0:
            return self.max_registration > self.active_registration_count()
        return True

    def promote_from_waitlist(self):
        """Rev 3 waitlist auto-promotion: fill freed seats from the
        waitlist in FIFO order and email each promoted member. Called
        after any capacity-freeing change (cancellation, reject,
        not-attending transition, cap increase). Promotion is direct
        (no claim window) — events are free, so there's nothing for the
        member to complete before the seat is theirs."""
        promoted = []
        while self.registration_allowed():
            next_in_line = (
                self.event_registrations.filter(state=EventRegistration.STATE_WAITLISTED)
                .order_by("created_at")
                .first()
            )
            if next_in_line is None:
                break
            next_in_line.state = EventRegistration.STATE_CONFIRMED
            next_in_line.save(update_fields=["state", "updated_at"])
            promoted.append(next_in_line)

        if promoted:
            from django.core.mail import send_mail

            for registration in promoted:
                send_mail(
                    subject=f"[null] You're in — seat confirmed for {self.name}",
                    message=(
                        f"Good news! A seat opened up for {self.descriptive_name()} "
                        f"and your waitlisted registration is now CONFIRMED.\n\n"
                        f"Event page: {settings.SITE_BASE_URL}{self.get_absolute_url()}\n\n"
                        f"If you can no longer attend, please cancel so the next "
                        f"person on the waitlist gets the seat."
                    ),
                    from_email=None,
                    recipient_list=[registration.user.email],
                    fail_silently=True,
                )
        return promoted

    def registration_active(self):
        if not self.accepting_registration:
            return False
        if self.registration_start_time and self.registration_end_time:
            now = timezone.now()
            return self.registration_start_time < now < self.registration_end_time
        return False

    def registerable_in_future(self):
        return bool(
            self.accepting_registration
            and self.registration_start_time
            and self.registration_start_time > timezone.now()
        )

    def register_name(self):
        return "Register" if self.invite_only() else "RSVP"

    def average_feedback_rating(self):
        from django.db.models import Avg

        return self.feedback.aggregate(avg=Avg("rating"))["avg"]

    def cancellation_deadline(self):
        """Moment after which cancelling counts as a no-show; None when
        the event allows cancelling anytime."""
        if not self.cancellation_deadline_hours:
            return None
        from datetime import timedelta

        return self.start_time - timedelta(hours=self.cancellation_deadline_hours)

    def image_url(self):
        return self.image.url if self.image else "/static/images/default_image.png"

    def to_ics_event(self):
        """Ports Event#to_ics_event — used by Chapter#upcoming_events_ics."""
        from icalendar import Event as ICalEvent
        from icalendar import vCalAddress, vText

        ics_event = ICalEvent()
        ics_event.add("dtstart", self.start_time)
        ics_event.add("dtend", self.end_time)
        ics_event.add("summary", self.descriptive_name())
        ics_event.add("description", self.description)
        ics_event.add("location", self.venue.map_url or self.venue.address)
        ics_event.add("created", self.created_at)
        ics_event.add("last-modified", self.updated_at)
        ics_event["uid"] = f"swachalit-event-{self.pk}"
        ics_event.add("url", self.get_absolute_url())
        organizer = vCalAddress("MAILTO:no-reply@null.community")
        organizer.params["cn"] = vText("null Open Security Community")
        ics_event["organizer"] = organizer
        return ics_event


class EventSession(TimeStampedModel, SoftDeleteModel):
    """Mirrors `event_sessions`. See app/models/event_session.rb.

    Voting: the original used acts_as_votable (a separate polymorphic
    `votes` table). django-vote was tried as a replacement but its
    bundled migrations use Meta.index_together, removed in Django 5.1
    — uninstallable on this stack. SessionVote (below) is a small
    first-party model instead: one row per (session, user), toggled
    up/down, same behavior as the original's like/dislike actions.
    """

    EDIT_WINDOW_DAYS = 30

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="event_sessions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_sessions"
    )
    name = models.CharField(max_length=255)
    session_type = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    tags = TaggableManager(blank=True)

    need_projector = models.BooleanField(default=False)
    need_microphone = models.BooleanField(default=False)
    need_whiteboard = models.BooleanField(default=False)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    slug = models.SlugField(max_length=255, blank=True, db_index=True)
    presentation_url = models.URLField(max_length=255, blank=True)
    placeholder = models.BooleanField(default=False)
    video_url = models.URLField(max_length=255, blank=True)
    image = models.ImageField(upload_to="sessions/", blank=True, null=True)

    # Rev 3: additional speakers credited on the session (the FK `user`
    # stays the primary speaker), and the speaker's explicit "yes, I'll
    # be there" — unconfirmed slots are flagged to leads.
    co_speakers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="co_speaker_sessions"
    )
    speaker_confirmed_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteQuerySet.as_manager()

    class Meta:
        db_table = "event_sessions"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("events:session_detail", args=[self.pk])

    def speaker(self):
        return self.user

    def speaker_name(self):
        return self.user.name if self.user_id else ""

    def all_speakers(self):
        """Primary speaker + co-speakers, primary first."""
        speakers = [self.user] if self.user_id else []
        speakers += [u for u in self.co_speakers.all() if u.pk != self.user_id]
        return speakers

    def confirm_speaker(self):
        if self.speaker_confirmed_at is None:
            self.speaker_confirmed_at = timezone.now()
            self.save(update_fields=["speaker_confirmed_at", "updated_at"])

    def is_editable(self):
        """Editable only within EDIT_WINDOW_DAYS of the event end (event.rb)."""
        return timezone.now() <= self.event.end_time + timezone.timedelta(days=self.EDIT_WINDOW_DAYS)

    def likes_count(self):
        return self.votes.filter(is_upvote=True).count()

    def dislikes_count(self):
        return self.votes.filter(is_upvote=False).count()


class SessionVote(TimeStampedModel):
    """First-party replacement for acts_as_votable — see EventSession
    docstring. One row per (session, user); is_upvote toggles between
    like/dislike, mirroring the original's voted_up_on?/voted_down_on?
    + likes/dislikes + unliked_by/undisliked_by toggle semantics.
    """

    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_votes")
    is_upvote = models.BooleanField()

    class Meta:
        db_table = "event_session_votes"
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="unique_vote_per_user_per_session"),
        ]


class EventSessionComment(TimeStampedModel):
    """Mirrors `event_session_comments`."""

    event_session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_comments")
    comment_body = models.TextField()

    class Meta:
        db_table = "event_session_comments"
        ordering = ["created_at"]


class EventRegistrationQuerySet(models.QuerySet):
    def absent(self):
        return self.filter(state=EventRegistration.STATE_ABSENT)


class EventRegistration(TimeStampedModel):
    """Mirrors `event_registrations`. See app/models/event_registration.rb."""

    STATE_PROVISIONAL = "Provisional"
    STATE_CONFIRMED = "Confirmed"
    STATE_NOT_ATTENDING = "Not Attending"
    STATE_ABSENT = "Absent"
    STATE_WAITLISTED = "Waitlisted"  # Rev 3: event full, queued FIFO

    STATE_CHOICES = [
        (STATE_PROVISIONAL, STATE_PROVISIONAL),
        (STATE_CONFIRMED, STATE_CONFIRMED),
        (STATE_NOT_ATTENDING, STATE_NOT_ATTENDING),
        (STATE_ABSENT, STATE_ABSENT),
        (STATE_WAITLISTED, STATE_WAITLISTED),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="event_registrations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    visible = models.BooleanField(default=True)
    accepted = models.BooleanField(null=True, blank=True)
    state = models.CharField(max_length=255, choices=STATE_CHOICES, blank=True)

    # Rev 3 check-in: opaque per-registration code (rendered as a QR),
    # and the moment attendance was recorded at the door.
    check_in_code = models.CharField(max_length=64, unique=True, null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    # Rev 3: answers to the event's custom registration questions
    # ({label: answer}) and the lead's note from the approval queue.
    custom_answers = models.JSONField(default=dict, blank=True)
    review_note = models.CharField(max_length=255, blank=True)

    objects = EventRegistrationQuerySet.as_manager()

    class Meta:
        db_table = "event_registrations"
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="unique_user_per_event_registration"),
        ]

    def clean(self):
        """Ported from EventRegistration#new_registration_validator (only
        ran on new_record? in Rails) — blocks RSVP when the event is full
        or outside its registration window.

        Raised as a non-field error (not keyed to "event"): "event" isn't
        a field on EventRegistrationForm (it's set programmatically, not
        user-editable), and ModelForm._post_clean() raises ValueError
        ("has no field named 'event'") if a model-level ValidationError
        tries to bind to a field the form doesn't expose — this used to
        crash the RSVP view with a 500 instead of showing the message.
        """
        super().clean()
        if self._state.adding:
            if not self.event.registration_active():
                raise ValidationError("Registration is not active for this event.")
            # Rev 3: a full event no longer rejects — save() waitlists
            # instead. But repeat no-shows are temporarily blocked.
            if self.user_id and self.user.rsvp_blocked():
                raise ValidationError(
                    "Your RSVP is temporarily blocked after "
                    f"{settings.NO_SHOW_STRIKE_LIMIT} recent no-shows. "
                    "Attend or cancel in time to clear your record."
                )

    def save(self, *args, **kwargs):
        """Ported from EventRegistration#set_default_state! (before_create):
        invite-only events start Provisional pending leader approval,
        open events are auto-Confirmed."""
        if self._state.adding and not self.state:
            if not self.event.registration_allowed():
                self.state = self.STATE_WAITLISTED
            elif self.event.invite_only():
                self.state = self.STATE_PROVISIONAL
            else:
                self.state = self.STATE_CONFIRMED
        if not self.check_in_code:
            import secrets

            self.check_in_code = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    def confirmed(self):
        return self.state == self.STATE_CONFIRMED

    def check_in(self):
        if self.checked_in_at is None:
            self.checked_in_at = timezone.now()
            if self.state != self.STATE_CONFIRMED:
                self.state = self.STATE_CONFIRMED
            self.save(update_fields=["checked_in_at", "state", "updated_at"])

    SEAT_HOLDING_STATES = (STATE_PROVISIONAL, STATE_CONFIRMED)

    def set_state(self, new_state):
        valid_states = dict(self.STATE_CHOICES)
        if new_state not in valid_states:
            raise ValueError("Invalid State")
        if self.state != new_state:
            freed_seat = self.state in self.SEAT_HOLDING_STATES and new_state not in self.SEAT_HOLDING_STATES
            self.state = new_state
            self.save(update_fields=["state", "updated_at"])
            if freed_seat:
                self.event.promote_from_waitlist()

    def waitlist_position(self):
        if self.state != self.STATE_WAITLISTED:
            return None
        return (
            self.event.event_registrations.filter(
                state=self.STATE_WAITLISTED, created_at__lt=self.created_at
            ).count()
            + 1
        )


class StarredSession(TimeStampedModel):
    """Rev 3 personal agenda: a member stars sessions to build their
    own schedule (my_schedule view + ICS feed)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="starred_sessions"
    )
    session = models.ForeignKey(EventSession, on_delete=models.CASCADE, related_name="stars")

    class Meta:
        db_table = "starred_sessions"
        constraints = [
            models.UniqueConstraint(fields=["user", "session"], name="one_star_per_session"),
        ]

    def __str__(self):
        return f"{self.user} ★ {self.session}"


class EventFeedback(TimeStampedModel):
    """Rev 3 post-event feedback: one rating (+optional comment) per
    attendee per event, requested by email after the event ends."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_feedback"
    )
    rating = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField(blank=True)

    class Meta:
        db_table = "event_feedback"
        constraints = [
            models.UniqueConstraint(fields=["event", "user"], name="one_feedback_per_attendee"),
        ]

    def __str__(self):
        return f"{self.user} rated {self.event}: {self.rating}"
