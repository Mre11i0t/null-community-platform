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
        {"event": event, "sessions": sessions, "user_registration": user_registration},
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

    return render(
        request,
        "events/session_detail.html",
        {
            "session": session,
            "comments": comments,
            "comment_form": EventSessionCommentForm(),
            "user_vote": user_vote,
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
            messages.success(request, "You have successfully registered with the event.")
            return redirect("events:detail", pk=event.pk)
    else:
        form = EventRegistrationForm(instance=blank_registration)

    return render(
        request,
        "events/registration_new.html",
        {"event": event, "form": form, "already_registered": already_registered},
    )


@login_required
def registration_destroy(request, event_id, pk):
    """Mirrors EventRegistrationsController#destroy — only the owning
    user can cancel their own registration."""
    event = get_object_or_404(Event, pk=event_id)
    registration = get_object_or_404(EventRegistration, pk=pk, event=event)
    if request.method == "POST" and registration.user_id == request.user.id:
        registration.delete()
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
