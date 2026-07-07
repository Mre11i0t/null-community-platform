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

    def registration_allowed(self):
        if self.max_registration and self.max_registration > 0:
            return self.max_registration > self.event_registrations.count()
        return True

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

    STATE_CHOICES = [
        (STATE_PROVISIONAL, STATE_PROVISIONAL),
        (STATE_CONFIRMED, STATE_CONFIRMED),
        (STATE_NOT_ATTENDING, STATE_NOT_ATTENDING),
        (STATE_ABSENT, STATE_ABSENT),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="event_registrations")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations"
    )
    visible = models.BooleanField(default=True)
    accepted = models.BooleanField(null=True, blank=True)
    state = models.CharField(max_length=255, choices=STATE_CHOICES, blank=True)

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
            if not self.event.registration_allowed():
                raise ValidationError("Registration is not allowed for this event (it is full).")
            if not self.event.registration_active():
                raise ValidationError("Registration is not active for this event.")

    def save(self, *args, **kwargs):
        """Ported from EventRegistration#set_default_state! (before_create):
        invite-only events start Provisional pending leader approval,
        open events are auto-Confirmed."""
        if self._state.adding and not self.state:
            self.state = self.STATE_PROVISIONAL if self.event.invite_only() else self.STATE_CONFIRMED
        super().save(*args, **kwargs)

    def confirmed(self):
        return self.state == self.STATE_CONFIRMED

    def set_state(self, new_state):
        valid_states = dict(self.STATE_CHOICES)
        if new_state not in valid_states:
            raise ValueError("Invalid State")
        if self.state != new_state:
            self.state = new_state
            self.save(update_fields=["state", "updated_at"])
