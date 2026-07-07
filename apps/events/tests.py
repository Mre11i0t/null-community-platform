import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event, EventRegistration, EventSessionComment, SessionVote
from tests.factories import (
    EventFactory,
    EventRegistrationFactory,
    EventSessionCommentFactory,
    EventSessionFactory,
    EventTypeFactory,
    UserFactory,
    VenueFactory,
)

pytestmark = pytest.mark.django_db


# --- detail / session_detail ------------------------------------------------


def test_event_detail_shows_sessions_and_no_registration_for_anonymous(client):
    event = EventFactory()
    session = EventSessionFactory(event=event)

    response = client.get(reverse("events:detail", args=[event.pk]))

    assert response.status_code == 200
    assert session in response.context["sessions"]
    assert response.context["user_registration"] is None


def test_event_detail_shows_the_users_own_registration(client):
    event = EventFactory()
    user = UserFactory()
    registration = EventRegistrationFactory(event=event, user=user)
    client.force_login(user)

    response = client.get(reverse("events:detail", args=[event.pk]))

    assert response.context["user_registration"] == registration


def test_session_detail_reports_authenticated_users_vote(client):
    session = EventSessionFactory()
    user = UserFactory()
    SessionVote.objects.create(session=session, user=user, is_upvote=True)
    client.force_login(user)

    response = client.get(reverse("events:session_detail", args=[session.pk]))

    assert response.status_code == 200
    assert response.context["user_vote"] == "up"


# --- RSVP: registration create/cancel + state machine + validation --------


def test_rsvp_creates_confirmed_registration_for_non_invite_only_event(client):
    event = EventFactory()
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert response.status_code == 302
    registration = EventRegistration.objects.get(event=event, user=user)
    assert registration.state == EventRegistration.STATE_CONFIRMED


def test_rsvp_creates_provisional_registration_for_invite_only_event(client):
    invite_only_type = EventTypeFactory(name="Invite Only Type", invitation_required=True)
    event = EventFactory(event_type=invite_only_type)
    user = UserFactory()
    client.force_login(user)

    client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    registration = EventRegistration.objects.get(event=event, user=user)
    assert registration.state == EventRegistration.STATE_PROVISIONAL


def test_rsvp_rejected_when_event_is_full(client):
    event = EventFactory(max_registration=1)
    EventRegistrationFactory(event=event)  # fills the only slot
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert response.status_code == 200  # re-renders the form with an error
    assert not EventRegistration.objects.filter(event=event, user=user).exists()
    assert response.context["form"].errors


def test_rsvp_rejected_outside_registration_window(client):
    event = EventFactory(
        registration_start_time=timezone.now() - datetime.timedelta(days=10),
        registration_end_time=timezone.now() - datetime.timedelta(days=1),
    )
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert response.status_code == 200
    assert not EventRegistration.objects.filter(event=event, user=user).exists()


def test_rsvp_requires_login(client):
    event = EventFactory()
    response = client.get(reverse("events:registration_new", args=[event.pk]))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_registration_cancel_only_works_for_owning_user(client):
    event = EventFactory()
    owner = UserFactory()
    other = UserFactory()
    registration = EventRegistrationFactory(event=event, user=owner)

    client.force_login(other)
    client.post(reverse("events:registration_destroy", args=[event.pk, registration.pk]))
    assert EventRegistration.objects.filter(pk=registration.pk).exists()

    client.force_login(owner)
    client.post(reverse("events:registration_destroy", args=[event.pk, registration.pk]))
    assert not EventRegistration.objects.filter(pk=registration.pk).exists()


def test_registration_index_only_shows_visible_registrations(client):
    event = EventFactory()
    visible = EventRegistrationFactory(event=event, visible=True)
    hidden = EventRegistrationFactory(event=event, visible=False)

    response = client.get(reverse("events:registration_index", args=[event.pk]))

    registrations = list(response.context["registrations"])
    assert visible in registrations
    assert hidden not in registrations


# --- Comments ----------------------------------------------------------------


def test_comment_create_requires_login(client):
    session = EventSessionFactory()
    response = client.post(
        reverse("events:comment_create", args=[session.pk]), {"comment_body": "hi"}
    )
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


def test_comment_create_success(client):
    session = EventSessionFactory()
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("events:comment_create", args=[session.pk]),
        {"comment_body": "Great talk!", "g-recaptcha-response": "PASSED"},
    )

    assert response.status_code == 302
    comment = EventSessionComment.objects.get(event_session=session, user=user)
    assert comment.comment_body == "Great talk!"


def test_comment_update_only_editable_by_owner(client):
    comment = EventSessionCommentFactory(comment_body="original")
    other_user = UserFactory()
    client.force_login(other_user)

    response = client.get(reverse("events:comment_update", args=[comment.pk]))
    assert response.status_code == 404

    client.force_login(comment.user)
    response = client.post(
        reverse("events:comment_update", args=[comment.pk]), {"comment_body": "edited"}
    )
    assert response.status_code == 302
    comment.refresh_from_db()
    assert comment.comment_body == "edited"


def test_comment_delete_only_by_owner(client):
    comment = EventSessionCommentFactory()
    other_user = UserFactory()

    client.force_login(other_user)
    client.post(reverse("events:comment_delete", args=[comment.pk]))
    assert EventSessionComment.objects.filter(pk=comment.pk).exists()

    client.force_login(comment.user)
    client.post(reverse("events:comment_delete", args=[comment.pk]))
    assert not EventSessionComment.objects.filter(pk=comment.pk).exists()


# --- Voting --------------------------------------------------------------


def test_session_like_toggles_on_then_off(client):
    session = EventSessionFactory()
    user = UserFactory()
    client.force_login(user)
    url = reverse("events:session_like", args=[session.pk])

    client.post(url)
    vote = SessionVote.objects.get(session=session, user=user)
    assert vote.is_upvote is True

    client.post(url)
    assert not SessionVote.objects.filter(session=session, user=user).exists()


def test_session_dislike_flips_an_existing_like(client):
    session = EventSessionFactory()
    user = UserFactory()
    SessionVote.objects.create(session=session, user=user, is_upvote=True)
    client.force_login(user)

    client.post(reverse("events:session_dislike", args=[session.pk]))

    vote = SessionVote.objects.get(session=session, user=user)
    assert vote.is_upvote is False


def test_likes_and_dislikes_count(client):
    session = EventSessionFactory()
    SessionVote.objects.create(session=session, user=UserFactory(), is_upvote=True)
    SessionVote.objects.create(session=session, user=UserFactory(), is_upvote=True)
    SessionVote.objects.create(session=session, user=UserFactory(), is_upvote=False)

    assert session.likes_count() == 2
    assert session.dislikes_count() == 1


# --- Venue detail / My Sessions --------------------------------------------


def test_venue_detail_renders_venue(client):
    venue = VenueFactory(name="Cyber Auditorium")
    response = client.get(reverse("venue_detail", args=[venue.pk]))
    assert response.status_code == 200
    assert response.context["venue"] == venue


def test_my_sessions_requires_login(client):
    response = client.get(reverse("events:my_sessions"))
    assert response.status_code == 302


def test_my_sessions_only_shows_own_sessions(client):
    speaker = UserFactory()
    other = UserFactory()
    own_session = EventSessionFactory(user=speaker)
    EventSessionFactory(user=other)

    client.force_login(speaker)
    response = client.get(reverse("events:my_sessions"))

    sessions = list(response.context["sessions"])
    assert sessions == [own_session]


# --- Rev 3 foundations: soft-delete, per-event ICS, tz display --------------


def test_soft_deleted_event_vanishes_from_public_pages_but_stays_in_db(client):
    event = EventFactory(
        public=True,
        start_time=timezone.now() + datetime.timedelta(days=3),
        end_time=timezone.now() + datetime.timedelta(days=3, hours=2),
    )
    assert client.get(reverse("events:detail", args=[event.pk])).status_code == 200

    event.soft_delete()

    assert client.get(reverse("events:detail", args=[event.pk])).status_code == 404
    response = client.get(reverse("core:home"))
    assert event not in response.context["events"]
    assert Event.objects.filter(pk=event.pk).exists()  # still in DB for admin

    event.restore()
    assert client.get(reverse("events:detail", args=[event.pk])).status_code == 200


def test_soft_deleted_session_404s_and_leaves_event_page(client):
    session = EventSessionFactory()
    session.soft_delete()

    assert client.get(reverse("events:session_detail", args=[session.pk])).status_code == 404
    response = client.get(reverse("events:detail", args=[session.event.pk]))
    assert session not in response.context["sessions"]


def test_lead_can_archive_event_but_other_chapters_lead_cannot(client):
    from tests.factories import ChapterLeadFactory

    event = EventFactory(
        start_time=timezone.now() + datetime.timedelta(days=3),
        end_time=timezone.now() + datetime.timedelta(days=3, hours=2),
    )
    outsider = ChapterLeadFactory()  # lead of a different chapter
    client.force_login(outsider.user)
    response = client.post(reverse("leads:event_delete", args=[event.pk]))
    event.refresh_from_db()
    assert response.status_code == 403 and event.deleted_at is None

    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)
    client.post(reverse("leads:event_delete", args=[event.pk]))
    event.refresh_from_db()
    assert event.deleted_at is not None


def test_venue_archive_blocked_while_upcoming_events_exist(client):
    from tests.factories import ChapterLeadFactory

    event = EventFactory(
        start_time=timezone.now() + datetime.timedelta(days=3),
        end_time=timezone.now() + datetime.timedelta(days=3, hours=2),
    )
    venue = event.venue
    lead = ChapterLeadFactory(chapter=venue.chapter)
    client.force_login(lead.user)

    client.post(reverse("leads:venue_delete", args=[venue.pk]))
    venue.refresh_from_db()
    assert venue.deleted_at is None  # blocked

    event.soft_delete()
    client.post(reverse("leads:venue_delete", args=[venue.pk]))
    venue.refresh_from_db()
    assert venue.deleted_at is not None


def test_per_event_ics_download(client):
    event = EventFactory(
        public=True,
        name="ICS Single Event",
        start_time=timezone.now() + datetime.timedelta(days=3),
        end_time=timezone.now() + datetime.timedelta(days=3, hours=2),
    )
    response = client.get(reverse("events:event_ics", args=[event.pk]))
    assert response.status_code == 200
    assert response["Content-Type"] == "text/calendar"
    body = response.content.decode()
    assert "BEGIN:VEVENT" in body and "ICS Single Event" in body

    event.public = False
    event.save()
    assert client.get(reverse("events:event_ics", args=[event.pk])).status_code == 404


def test_with_tz_filter_appends_ist_label():
    from apps.core.templatetags.core_extras import with_tz

    dt = timezone.now()
    rendered = with_tz(dt)
    assert rendered.endswith("IST")
    assert with_tz(None) == ""
