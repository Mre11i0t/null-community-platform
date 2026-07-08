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


def test_rsvp_sends_confirmation_email_to_member(client):
    """PRD Part 7: a member gets a registration-confirmation email on a
    successful (confirmed) RSVP. The pre-fix code sent no email at all."""
    from django.core import mail

    event = EventFactory()
    user = UserFactory(email="rsvp@example.com")
    client.force_login(user)

    mail.outbox.clear()  # drop the admin-on-create email fired by EventFactory
    client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["rsvp@example.com"]
    assert event.name in msg.subject
    # No check-in code when the event has check-in disabled (the default).
    assert "Check-in code" not in msg.body


def test_rsvp_confirmation_email_carries_check_in_code_when_enabled(client):
    """PRD 3.7: when the event opts into on-site check-in, the confirmation
    email carries the member's check-in code + QR-pass link."""
    from django.core import mail

    event = EventFactory(check_in_enabled=True)
    user = UserFactory()
    client.force_login(user)

    mail.outbox.clear()  # drop the admin-on-create email fired by EventFactory
    client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    registration = EventRegistration.objects.get(event=event, user=user)
    body = mail.outbox[0].body
    assert "Check-in code" in body
    assert registration.check_in_code in body
    assert f"/registrations/{registration.pk}/qr.png" in body


def test_invite_only_rsvp_sends_no_confirmation_email(client):
    """A provisional (invite-only) RSVP is not yet confirmed, so no
    confirmation email fires — it waits for leader approval."""
    from django.core import mail

    invite_only_type = EventTypeFactory(name="Invite Only Confirm Test", invitation_required=True)
    event = EventFactory(event_type=invite_only_type)
    client.force_login(UserFactory())

    mail.outbox.clear()  # drop the admin-on-create email fired by EventFactory
    client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert mail.outbox == []


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


def test_rsvp_when_event_is_full_waitlists(client):
    """Rev 3 behavior change: a full event queues the RSVP instead of
    rejecting it (the pre-Rev-3 port re-rendered the form with an error)."""
    event = EventFactory(max_registration=1)
    EventRegistrationFactory(event=event)  # fills the only slot
    user = UserFactory()
    client.force_login(user)

    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )

    assert response.status_code == 302
    registration = EventRegistration.objects.get(event=event, user=user)
    assert registration.state == EventRegistration.STATE_WAITLISTED


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
    response = client.get(reverse("core:upcoming"))
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


# --- Rev 3 check-in (per-event opt-in) ---------------------------------------


def _check_in_event(**kwargs):
    return EventFactory(
        public=True,
        check_in_enabled=True,
        start_time=timezone.now() - datetime.timedelta(hours=1),
        end_time=timezone.now() + datetime.timedelta(hours=2),
        **kwargs,
    )


def test_registration_gets_check_in_code_on_create():
    registration = EventRegistrationFactory()
    assert registration.check_in_code and len(registration.check_in_code) >= 16


def test_check_in_pages_404_when_flag_disabled(client):
    from tests.factories import ChapterLeadFactory

    event = EventFactory(
        check_in_enabled=False,
        start_time=timezone.now() + datetime.timedelta(days=1),
        end_time=timezone.now() + datetime.timedelta(days=1, hours=2),
    )
    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)
    assert client.get(reverse("leads:check_in_dashboard", args=[event.pk])).status_code == 404
    assert client.get(reverse("leads:check_in_scan", args=[event.pk])).status_code == 404


def test_scanner_marks_registration_by_code(client):
    from tests.factories import ChapterLeadFactory

    event = _check_in_event()
    registration = EventRegistrationFactory(event=event)
    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)

    response = client.post(
        reverse("leads:check_in_mark", args=[event.pk]), {"code": registration.check_in_code}
    )
    data = response.json()
    assert data["ok"] and not data["already_checked_in"]
    registration.refresh_from_db()
    assert registration.checked_in_at is not None

    # second scan reports duplicate instead of double-counting
    data = client.post(
        reverse("leads:check_in_mark", args=[event.pk]), {"code": registration.check_in_code}
    ).json()
    assert data["ok"] and data["already_checked_in"]

    # unknown code
    response = client.post(reverse("leads:check_in_mark", args=[event.pk]), {"code": "nope"})
    assert response.status_code == 404


def test_kiosk_token_flow_without_login(client):
    from django.core import signing

    event = _check_in_event()
    registration = EventRegistrationFactory(event=event)
    token = signing.dumps({"event": event.pk}, salt="event-kiosk")

    url = reverse("leads:kiosk", args=[event.pk, token])
    response = client.get(url, {"q": registration.user.name[:5]})
    assert response.status_code == 200
    assert registration in response.context["results"]

    client.post(url, {"registration_id": registration.pk})
    registration.refresh_from_db()
    assert registration.checked_in_at is not None

    # tampered token 404s
    bad = reverse("leads:kiosk", args=[event.pk, token + "x"])
    assert client.get(bad).status_code == 404


def test_registration_qr_only_for_owner_or_lead(client):
    event = _check_in_event()
    registration = EventRegistrationFactory(event=event)
    url = reverse("events:registration_qr", args=[event.pk, registration.pk])

    client.force_login(registration.user)
    response = client.get(url)
    assert response.status_code == 200 and response["Content-Type"] == "image/png"

    stranger = UserFactory()
    client.force_login(stranger)
    assert client.get(url).status_code == 404


def test_auto_absent_only_when_both_flags_and_event_over():
    from apps.events.tasks import auto_mark_absent

    past = dict(
        start_time=timezone.now() - datetime.timedelta(hours=5),
        end_time=timezone.now() - datetime.timedelta(hours=3),
    )
    flagged = EventFactory(public=True, check_in_enabled=True, auto_absent_enabled=True, **past)
    unflagged = EventFactory(public=True, check_in_enabled=True, auto_absent_enabled=False, **past)

    no_show = EventRegistrationFactory(event=flagged)
    no_show.set_state(EventRegistration.STATE_CONFIRMED)
    attended = EventRegistrationFactory(event=flagged)
    attended.set_state(EventRegistration.STATE_CONFIRMED)
    attended.check_in()
    unflagged_reg = EventRegistrationFactory(event=unflagged)
    unflagged_reg.set_state(EventRegistration.STATE_CONFIRMED)

    assert auto_mark_absent() == 1

    no_show.refresh_from_db(); attended.refresh_from_db(); unflagged_reg.refresh_from_db()
    assert no_show.state == EventRegistration.STATE_ABSENT
    assert attended.state == EventRegistration.STATE_CONFIRMED
    assert unflagged_reg.state == EventRegistration.STATE_CONFIRMED  # untouched: flag off

    # idempotent — second run processes nothing
    assert auto_mark_absent() == 0


# --- Rev 3 registration upgrades ---------------------------------------------


def _open_event(**kwargs):
    """Public event with an active registration window."""
    defaults = dict(
        public=True,
        accepting_registration=True,
        registration_start_time=timezone.now() - datetime.timedelta(days=1),
        registration_end_time=timezone.now() + datetime.timedelta(days=1),
        start_time=timezone.now() + datetime.timedelta(days=2),
        end_time=timezone.now() + datetime.timedelta(days=2, hours=3),
    )
    defaults.update(kwargs)
    return EventFactory(**defaults)


def test_full_event_waitlists_instead_of_rejecting(client):
    event = _open_event(max_registration=1)
    EventRegistrationFactory(event=event)  # takes the only seat

    user = UserFactory()
    client.force_login(user)
    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )
    assert response.status_code == 302
    registration = event.event_registrations.get(user=user)
    assert registration.state == EventRegistration.STATE_WAITLISTED
    assert registration.waitlist_position() == 1


def test_waitlist_auto_promotes_fifo_and_emails(client):
    from django.core import mail

    event = _open_event(max_registration=1)
    seat_holder = EventRegistrationFactory(event=event)
    first = EventRegistrationFactory(event=event)   # waitlisted
    second = EventRegistrationFactory(event=event)  # waitlisted
    assert first.state == second.state == EventRegistration.STATE_WAITLISTED

    mail.outbox.clear()
    client.force_login(seat_holder.user)
    client.post(reverse("events:registration_destroy", args=[event.pk, seat_holder.pk]))

    first.refresh_from_db(); second.refresh_from_db()
    assert first.state == EventRegistration.STATE_CONFIRMED   # FIFO
    assert second.state == EventRegistration.STATE_WAITLISTED
    assert len(mail.outbox) == 1 and first.user.email in mail.outbox[0].to


def test_cancellation_after_deadline_counts_as_no_show(client):
    event = _open_event(
        cancellation_deadline_hours=72,  # deadline already passed (event in 2 days)
        max_registration=0,
    )
    registration = EventRegistrationFactory(event=event)
    assert registration.state == EventRegistration.STATE_CONFIRMED

    client.force_login(registration.user)
    client.post(reverse("events:registration_destroy", args=[event.pk, registration.pk]))

    registration.refresh_from_db()
    assert registration.state == EventRegistration.STATE_ABSENT  # strike, not delete


def test_rsvp_blocked_after_strike_limit(client, settings):
    settings.NO_SHOW_STRIKE_LIMIT = 2
    user = UserFactory()
    for _ in range(2):
        past = EventFactory(
            public=True,
            start_time=timezone.now() - datetime.timedelta(days=10),
            end_time=timezone.now() - datetime.timedelta(days=10, hours=-2),
        )
        registration = EventRegistrationFactory(event=past, user=user)
        registration.set_state(EventRegistration.STATE_ABSENT)

    assert user.rsvp_blocked()
    event = _open_event()
    client.force_login(user)
    response = client.post(
        reverse("events:registration_new", args=[event.pk]),
        {"visible": "on", "g-recaptcha-response": "PASSED"},
    )
    assert response.status_code == 200  # re-renders with error
    assert not event.event_registrations.filter(user=user).exists()
    assert "temporarily blocked" in response.content.decode()


def test_custom_questions_collected_at_rsvp_and_required_enforced(client):
    event = _open_event(
        custom_questions=[
            {"label": "T-shirt size", "required": True},
            {"label": "Dietary needs", "required": False},
        ]
    )
    user = UserFactory()
    client.force_login(user)
    url = reverse("events:registration_new", args=[event.pk])

    # missing required answer re-renders
    response = client.post(url, {"visible": "on", "g-recaptcha-response": "PASSED"})
    assert response.status_code == 200
    assert not event.event_registrations.filter(user=user).exists()

    response = client.post(
        url,
        {
            "visible": "on",
            "g-recaptcha-response": "PASSED",
            "custom_q_0": "XL",
            "custom_q_1": "",
        },
    )
    assert response.status_code == 302
    registration = event.event_registrations.get(user=user)
    assert registration.custom_answers == {"T-shirt size": "XL", "Dietary needs": ""}


def test_approval_queue_approve_and_reject(client):
    from django.core import mail

    from tests.factories import ChapterLeadFactory, EventTypeFactory

    invite_type = EventTypeFactory(name="Invite Workshop", invitation_required=True)
    event = _open_event(event_type=invite_type)
    approve_me = EventRegistrationFactory(event=event)
    reject_me = EventRegistrationFactory(event=event)
    assert approve_me.state == EventRegistration.STATE_PROVISIONAL

    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)

    response = client.get(reverse("leads:approval_queue", args=[event.pk]))
    assert approve_me in response.context["pending"] and reject_me in response.context["pending"]

    mail.outbox.clear()
    client.post(
        reverse("leads:approval_decide", args=[event.pk, approve_me.pk]), {"decision": "approve"}
    )
    client.post(
        reverse("leads:approval_decide", args=[event.pk, reject_me.pk]),
        {"decision": "reject", "note": "Full house this time"},
    )

    approve_me.refresh_from_db(); reject_me.refresh_from_db()
    assert approve_me.state == EventRegistration.STATE_CONFIRMED
    assert reject_me.state == EventRegistration.STATE_NOT_ATTENDING
    assert reject_me.review_note == "Full house this time"
    assert len(mail.outbox) == 2


# --- Rev 3 personal agenda ---------------------------------------------------


def test_star_toggle_and_my_schedule(client):
    session = EventSessionFactory(name="Starrable Talk")
    user = UserFactory()
    client.force_login(user)

    client.post(reverse("events:session_star", args=[session.pk]))
    response = client.get(reverse("events:my_schedule"))
    assert any(star.session == session for star in response.context["stars"])

    ics = client.get(reverse("events:my_schedule_ics"))
    assert ics["Content-Type"] == "text/calendar"
    assert "Starrable Talk" in ics.content.decode()

    # toggle off
    client.post(reverse("events:session_star", args=[session.pk]))
    response = client.get(reverse("events:my_schedule"))
    assert len(response.context["stars"]) == 0


# --- Rev 3 engagement ----------------------------------------------------------


def test_event_discussion_thread(client):
    event = EventFactory(public=True)
    user = UserFactory()
    client.force_login(user)

    client.post(reverse("events:event_comment_create", args=[event.pk]), {"body": "Parking nearby?"})
    response = client.get(reverse("events:detail", args=[event.pk]))
    assert any(c.body == "Parking nearby?" for c in response.context["event_comments"])


def test_photo_upload_leads_only(client):
    import io

    from PIL import Image

    from tests.factories import ChapterLeadFactory

    event = EventFactory(public=True)

    def png():
        buf = io.BytesIO()
        Image.new("RGB", (4, 4)).save(buf, format="PNG")
        buf.seek(0)
        buf.name = "photo.png"
        return buf

    stranger = UserFactory()
    client.force_login(stranger)
    client.post(reverse("events:event_photo_upload", args=[event.pk]), {"image": png()})
    assert event.photos.count() == 0

    lead = ChapterLeadFactory(chapter=event.chapter)
    client.force_login(lead.user)
    client.post(
        reverse("events:event_photo_upload", args=[event.pk]),
        {"image": png(), "caption": "Group shot"},
    )
    assert event.photos.count() == 1


def test_session_qa_post_upvote_and_moderation(client):
    from apps.events.models import SessionQuestion
    from tests.factories import ChapterLeadFactory

    session = EventSessionFactory()
    asker = UserFactory()
    client.force_login(asker)
    client.post(
        reverse("events:question_create", args=[session.pk]), {"question": "Slides later?"}
    )
    question = SessionQuestion.objects.get()
    assert question.upvote_count() == 1  # own upvote

    voter = UserFactory()
    client.force_login(voter)
    client.post(reverse("events:question_upvote", args=[question.pk]))
    assert question.upvote_count() == 2
    client.post(reverse("events:question_upvote", args=[question.pk]))  # toggle off
    assert question.upvote_count() == 1

    # moderation is lead-only
    client.post(reverse("events:question_hide", args=[question.pk]))
    question.refresh_from_db()
    assert not question.is_hidden

    lead = ChapterLeadFactory(chapter=session.event.chapter)
    client.force_login(lead.user)
    client.post(reverse("events:question_hide", args=[question.pk]))
    question.refresh_from_db()
    assert question.is_hidden

    response = client.get(reverse("events:session_detail", args=[session.pk]))
    assert question not in response.context["questions"]


def test_gamification_points_badges_and_leaderboard(client):
    from apps.core.gamification import user_badges, user_points

    chapter_event = EventFactory(
        public=True,
        start_time=timezone.now() - datetime.timedelta(days=3),
        end_time=timezone.now() - datetime.timedelta(days=3, hours=-2),
    )
    speaker = UserFactory()
    EventSessionFactory(event=chapter_event, user=speaker, placeholder=False)
    registration = EventRegistrationFactory(event=chapter_event, user=speaker)
    registration.set_state(EventRegistration.STATE_CONFIRMED)

    assert user_points(speaker) == 60  # 50 talk + 10 attended
    assert any(b["slug"] == "first-talk" for b in user_badges(speaker))

    sub = chapter_event.chapter.subdomain
    response = client.get("/leaderboard", HTTP_HOST=f"{sub}.localhost")
    assert response.status_code == 200
    assert response.context["rows"][0]["user"] == speaker

    # leaderboard is chapter-site only
    assert client.get("/leaderboard").status_code == 404


def test_member_self_reports_achievement(client):
    from apps.proposals.models import UserAchievement

    user = UserFactory()
    client.force_login(user)
    response = client.post(
        reverse("accounts:add_achievement"),
        {
            "achievement_type": UserAchievement.TYPE_BUG_BOUNTY,
            "info": "Bounty from ExampleCorp",
            "reference": "https://example.com/hof",
        },
    )
    assert response.status_code == 302
    achievement = UserAchievement.objects.get(user=user)
    assert achievement.source == UserAchievement.SOURCE_SELF
