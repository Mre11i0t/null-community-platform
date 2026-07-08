from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import EventRegistrationForm, EventSessionCommentForm
from .models import Event, EventRegistration, EventSession, EventSessionComment, SessionVote, Venue


def detail(request, pk):
    """Mirrors EventsController#show."""
    event = get_object_or_404(
        Event.objects.alive().select_related("chapter", "venue", "event_type"), pk=pk
    )
    sessions = event.event_sessions.alive().select_related("user").order_by("start_time")

    user_registration = None
    if request.user.is_authenticated:
        user_registration = event.event_registrations.filter(user=request.user).first()

    return render(
        request,
        "events/detail.html",
        {
            "event": event,
            "sessions": sessions,
            "user_registration": user_registration,
            "event_comments": event.comments.select_related("user").order_by("created_at"),
            "event_photos": event.photos.order_by("-created_at"),
            "can_manage": request.user.is_authenticated
            and request.user.managed_chapter(event.chapter),
        },
    )


def session_detail(request, pk):
    """Mirrors EventSessionsController#show + the _reaction.html.erb
    partial (comments + like/dislike). The original used AJAX
    (remote: true) for voting/commenting/inline-edit; this is a
    server-rendered equivalent — same actions and end state, full page
    reload instead of in-place DOM updates.
    """
    session = get_object_or_404(
        EventSession.objects.alive().select_related("event", "user"), pk=pk
    )
    comments = session.comments.select_related("user").order_by("-created_at")

    user_vote = None
    if request.user.is_authenticated:
        vote = SessionVote.objects.filter(session=session, user=request.user).first()
        user_vote = "up" if vote and vote.is_upvote else "down" if vote else None

    from django.db.models import Count

    questions = (
        session.questions.filter(is_hidden=False)
        .select_related("user")
        .annotate(votes_count=Count("upvoters"))
        .order_by("-votes_count", "created_at")
    )
    return render(
        request,
        "events/session_detail.html",
        {
            "session": session,
            "comments": comments,
            "comment_form": EventSessionCommentForm(),
            "user_vote": user_vote,
            "questions": questions,
            "can_moderate": request.user.is_authenticated
            and request.user.managed_chapter(session.event.chapter),
        },
    )


@login_required
def session_like(request, pk):
    """Mirrors EventSessionsController#like — toggles the upvote."""
    session = get_object_or_404(EventSession, pk=pk)
    if request.method == "POST":
        vote = SessionVote.objects.filter(session=session, user=request.user).first()
        if vote and vote.is_upvote:
            vote.delete()
        elif vote:
            vote.is_upvote = True
            vote.save()
        else:
            SessionVote.objects.create(session=session, user=request.user, is_upvote=True)
    return redirect("events:session_detail", pk=session.pk)


@login_required
def session_dislike(request, pk):
    """Mirrors EventSessionsController#dislike — toggles the downvote."""
    session = get_object_or_404(EventSession, pk=pk)
    if request.method == "POST":
        vote = SessionVote.objects.filter(session=session, user=request.user).first()
        if vote and not vote.is_upvote:
            vote.delete()
        elif vote:
            vote.is_upvote = False
            vote.save()
        else:
            SessionVote.objects.create(session=session, user=request.user, is_upvote=False)
    return redirect("events:session_detail", pk=session.pk)


@login_required
def comment_create(request, session_id):
    """Mirrors EventSessionCommentsController#create."""
    session = get_object_or_404(EventSession, pk=session_id)
    if request.method == "POST":
        form = EventSessionCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.event_session = session
            comment.user = request.user
            comment.save()
            messages.success(request, "Comment added successfully")
        else:
            messages.error(request, "Failed to add comment")
    return redirect("events:session_detail", pk=session.pk)


@login_required
def comment_update(request, pk):
    """Mirrors EventSessionCommentsController#edit/#update — owner only.
    Original used an inline AJAX-toggled edit form; this is a small
    standalone edit page instead (GET shows it, POST saves)."""
    comment = get_object_or_404(EventSessionComment, pk=pk, user=request.user)
    if request.method == "POST":
        comment.comment_body = request.POST.get("comment_body", comment.comment_body)
        comment.save()
        messages.success(request, "Comment updated successfully")
        return redirect("events:session_detail", pk=comment.event_session_id)
    return render(request, "events/comment_edit.html", {"comment": comment})


@login_required
def comment_delete(request, pk):
    """Mirrors EventSessionCommentsController#destroy — owner only."""
    comment = get_object_or_404(EventSessionComment, pk=pk, user=request.user)
    session_id = comment.event_session_id
    if request.method == "POST":
        comment.delete()
        messages.success(request, "Comment deleted successfully")
    return redirect("events:session_detail", pk=session_id)


@login_required
def registration_new(request, event_id):
    """Mirrors EventRegistrationsController#new/#create. GET shows the
    form (or the relevant "not allowed" alert, ported from
    event_registrations/new.html.erb); POST creates the registration.
    """
    event = get_object_or_404(
        Event.objects.alive().select_related("chapter", "venue", "event_type"), pk=event_id
    )
    already_registered = event.event_registrations.filter(user=request.user).exists()
    # event/user must be set on the instance before is_valid() runs, since
    # ModelForm's _post_clean() calls instance.full_clean() -> our
    # clean() -> event.registration_allowed() internally.
    blank_registration = EventRegistration(event=event, user=request.user)

    if request.method == "POST":
        form = EventRegistrationForm(request.POST, instance=blank_registration)
        if form.is_valid():
            registration = form.save()
            if registration.state == EventRegistration.STATE_WAITLISTED:
                messages.info(
                    request,
                    f"This event is full — you are #{registration.waitlist_position()} on the "
                    "waitlist. We'll email you the moment a seat opens up.",
                )
            else:
                messages.success(request, "You have successfully registered with the event.")
                if registration.confirmed():
                    _send_registration_confirmation(registration)
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventRegistrationForm(instance=blank_registration)

    return render(
        request,
        "events/registration_new.html",
        {"event": event, "form": form, "already_registered": already_registered},
    )


def _send_registration_confirmation(registration):
    """Rev 3 / PRD Part 7: email the member on a successful RSVP. When the
    event has on-site check-in enabled, the mail also carries the check-in
    code + a link to the QR pass (which otherwise only appeared on the RSVP
    page — see PRD 3.7). fail_silently so a mail hiccup never breaks the RSVP."""
    from django.conf import settings
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.urls import reverse

    event = registration.event
    user = registration.user
    if not user or not user.email:
        return
    base = event.chapter.site_url()
    check_in = event.check_in_enabled
    context = {
        "registration": registration,
        "event": event,
        "event_url": base + reverse("events:detail", args=[event.pk]),
        "check_in_code": registration.check_in_code if check_in else "",
        "qr_url": (base + reverse("events:registration_qr", args=[event.pk, registration.pk])) if check_in else "",
    }
    body = render_to_string("events/emails/registration_confirmation.txt", context)
    send_mail(
        f"You're registered: {event.descriptive_name()}",
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )


@login_required
def registration_destroy(request, event_id, pk):
    """Mirrors EventRegistrationsController#destroy — only the owning
    user can cancel their own registration."""
    event = get_object_or_404(Event, pk=event_id)
    registration = get_object_or_404(EventRegistration, pk=pk, event=event)
    if request.method == "POST" and registration.user_id == request.user.id:
        deadline = event.cancellation_deadline()
        held_seat = registration.state in EventRegistration.SEAT_HOLDING_STATES
        if deadline and timezone.now() > deadline and held_seat:
            # Rev 3: cancelling inside the deadline window counts as a
            # no-show strike instead of silently freeing the seat.
            registration.set_state(EventRegistration.STATE_ABSENT)
            messages.warning(
                request,
                "The cancellation deadline has passed, so this counts as a "
                "no-show on your record. The seat has been released to the waitlist.",
            )
        else:
            registration.delete()
            if held_seat:
                event.promote_from_waitlist()
            messages.success(request, "You have successfully unregistered with the event.")
    return redirect("events:detail", pk=event.pk)


def event_ics(request, pk):
    """Single-event ICS download (Rev 3 roadmap #1) — lets an attendee
    add just this event to their calendar, complementing the chapter-wide
    feed at /chapters/<pk>/calendar.ics."""
    from icalendar import Calendar

    event = get_object_or_404(Event.objects.public_events(), pk=pk)
    cal = Calendar()
    cal.add("version", "2.0")
    cal.add("prodid", "-//null Community Platform//null.community//")
    cal.add_component(event.to_ics_event())
    from django.http import HttpResponse

    return HttpResponse(
        cal.to_ical(),
        content_type="text/calendar",
        headers={"Content-Disposition": f'inline; filename="event-{event.pk}.ics"'},
    )


def venue_detail(request, pk):
    """Mirrors VenuesController#show / the `_venue` partial (address + map embed)."""
    venue = get_object_or_404(Venue.objects.alive(), pk=pk)
    return render(request, "events/venue_detail.html", {"venue": venue})


@login_required
def my_sessions(request):
    """Mirrors EventSessionsController#my_sessions."""
    sessions = request.user.speaker_sessions().select_related("event", "event__chapter")
    return render(request, "events/my_sessions.html", {"sessions": sessions, "now": timezone.now()})


def registration_index(request, event_id):
    """Mirrors EventRegistrationsController#index — avatar grid of
    visible registrations."""
    event = get_object_or_404(Event, pk=event_id)
    registrations = event.event_registrations.filter(visible=True).select_related("user")
    return render(
        request, "events/registration_index.html", {"event": event, "registrations": registrations}
    )


@login_required
def registration_qr(request, event_id, pk):
    """PNG QR of the registration's check-in code — shown on the event
    page to the registration's owner when the event has check-in enabled.
    The QR encodes the opaque code only (no URL, no PII)."""
    import io

    import qrcode
    from django.http import Http404, HttpResponse

    event = get_object_or_404(Event.objects.alive(), pk=event_id)
    registration = get_object_or_404(EventRegistration, pk=pk, event=event)
    if not event.check_in_enabled:
        raise Http404
    is_owner = registration.user_id == request.user.id
    is_lead = request.user.managed_chapter(event.chapter)
    if not (is_owner or is_lead):
        raise Http404

    img = qrcode.make(registration.check_in_code, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return HttpResponse(buf.getvalue(), content_type="image/png")


@login_required
def session_confirm(request, pk):
    """Rev 3 speaker confirmation: the assigned speaker explicitly
    confirms their slot; unconfirmed slots are flagged to leads."""
    session = get_object_or_404(EventSession.objects.alive(), pk=pk, user=request.user)
    if request.method == "POST":
        session.confirm_speaker()
        messages.success(request, f'Slot confirmed for "{session.name}" — thank you!')
    return redirect("events:my_sessions")


@login_required
def session_star(request, pk):
    """Toggle a star (personal agenda)."""
    from .models import StarredSession

    session = get_object_or_404(EventSession.objects.alive(), pk=pk)
    if request.method == "POST":
        star, created = StarredSession.objects.get_or_create(user=request.user, session=session)
        if not created:
            star.delete()
            messages.info(request, "Removed from your schedule.")
        else:
            messages.success(request, "Added to your schedule.")
    return redirect("events:session_detail", pk=session.pk)


@login_required
def my_schedule(request):
    """The member's starred sessions, upcoming first."""
    from .models import StarredSession

    stars = (
        StarredSession.objects.filter(user=request.user, session__deleted_at__isnull=True)
        .select_related("session", "session__event", "session__event__chapter", "session__user")
        .order_by("session__start_time")
    )
    return render(
        request,
        "events/my_schedule.html",
        {"stars": stars, "now": timezone.now()},
    )


@login_required
def my_schedule_ics(request):
    """ICS of the member's starred sessions — subscribable."""
    from icalendar import Calendar, Event as IcsEvent
    from icalendar import vText

    from django.http import HttpResponse

    from .models import StarredSession

    cal = Calendar()
    cal.add("x-wr-calname", "My null schedule")
    cal.add("version", "2.0")
    cal.add("prodid", "-//null Community Platform//null.community//")
    stars = StarredSession.objects.filter(
        user=request.user, session__deleted_at__isnull=True
    ).select_related("session", "session__event", "session__event__venue")
    for star in stars:
        session = star.session
        ics = IcsEvent()
        ics["uid"] = f"swachalit-session-{session.pk}"
        ics.add("summary", session.name)
        ics.add("dtstart", session.start_time)
        ics.add("dtend", session.end_time)
        ics.add("location", vText(session.event.venue.name))
        cal.add_component(ics)
    return HttpResponse(
        cal.to_ical(),
        content_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="my-schedule.ics"'},
    )


@login_required
def event_feedback(request, event_id):
    """Rev 3 post-event feedback: 1-5 rating + comment, one per
    attendee, only after the event has ended."""
    from django.http import Http404

    from .models import EventFeedback

    event = get_object_or_404(Event.objects.alive(), pk=event_id)
    if event.end_time > timezone.now():
        raise Http404("Feedback opens after the event ends.")
    registration = event.event_registrations.filter(user=request.user).first()
    if registration is None:
        raise Http404("Feedback is for attendees.")

    existing = EventFeedback.objects.filter(event=event, user=request.user).first()
    if request.method == "POST":
        try:
            rating = int(request.POST.get("rating", 0))
        except ValueError:
            rating = 0
        if 1 <= rating <= 5:
            EventFeedback.objects.update_or_create(
                event=event,
                user=request.user,
                defaults={"rating": rating, "comment": request.POST.get("comment", "").strip()},
            )
            messages.success(request, "Thanks — your feedback is in!")
            return redirect("events:detail", pk=event.pk)
        messages.error(request, "Pick a rating between 1 and 5.")
    return render(request, "events/feedback.html", {"event": event, "existing": existing})


# --- Rev 3 engagement --------------------------------------------------------


@login_required
def event_comment_create(request, event_id):
    """Discussion thread on the event page (pre-event Q&A)."""
    from .models import EventComment

    event = get_object_or_404(Event.objects.alive(), pk=event_id)
    if request.method == "POST":
        body = (request.POST.get("body") or "").strip()
        if body:
            EventComment.objects.create(event=event, user=request.user, body=body[:2000])
            messages.success(request, "Comment posted.")
    return redirect("events:detail", pk=event.pk)


@login_required
def event_photo_upload(request, event_id):
    """Leads add post-event photos to the gallery."""
    from .models import EventPhoto

    event = get_object_or_404(Event.objects.alive(), pk=event_id)
    if not request.user.managed_chapter(event.chapter):
        from django.http import Http404

        raise Http404
    if request.method == "POST" and request.FILES.get("image"):
        EventPhoto.objects.create(
            event=event,
            uploaded_by=request.user,
            image=request.FILES["image"],
            caption=request.POST.get("caption", "").strip()[:255],
        )
        messages.success(request, "Photo added to the gallery.")
    return redirect("events:detail", pk=event.pk)


@login_required
def question_create(request, pk):
    """Audience Q&A: post a question on a session."""
    from .models import SessionQuestion

    session = get_object_or_404(EventSession.objects.alive(), pk=pk)
    if request.method == "POST":
        text = (request.POST.get("question") or "").strip()
        if text:
            question = SessionQuestion.objects.create(
                session=session, user=request.user, question=text[:500]
            )
            question.upvoters.add(request.user)  # your own question starts at 1
            messages.success(request, "Question submitted.")
    return redirect("events:session_detail", pk=session.pk)


@login_required
def question_upvote(request, pk):
    from .models import SessionQuestion

    question = get_object_or_404(SessionQuestion, pk=pk, is_hidden=False)
    if request.method == "POST":
        if question.upvoters.filter(pk=request.user.pk).exists():
            question.upvoters.remove(request.user)
        else:
            question.upvoters.add(request.user)
    return redirect("events:session_detail", pk=question.session_id)


@login_required
def question_hide(request, pk):
    """Moderation: leads of the owning chapter hide off-topic questions."""
    from django.http import Http404

    from .models import SessionQuestion

    question = get_object_or_404(SessionQuestion.objects.select_related("session__event"), pk=pk)
    if not request.user.managed_chapter(question.session.event.chapter):
        raise Http404
    if request.method == "POST":
        question.is_hidden = True
        question.save(update_fields=["is_hidden", "updated_at"])
        messages.info(request, "Question hidden.")
    return redirect("events:session_detail", pk=question.session_id)


def detail_by_name(request, name):
    """Ports the original's /event/:name SEO alias (EventsController
    #show_by_name) — resolves a slug to the canonical event URL."""
    event = Event.objects.public_events().filter(slug=name).order_by("-start_time").first()
    if event is None:
        from django.http import Http404

        raise Http404
    # Permanent (301): the slug alias exists only to consolidate link
    # equity onto the canonical /events/:id URL, so search engines should
    # treat it as a permanent move rather than a temporary redirect.
    return redirect("events:detail", pk=event.pk, permanent=True)
