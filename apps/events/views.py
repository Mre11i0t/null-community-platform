from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import EventRegistrationForm
from .models import Event, EventRegistration, EventSession


def detail(request, pk):
    """Mirrors EventsController#show."""
    event = get_object_or_404(
        Event.objects.select_related("chapter", "venue", "event_type"), pk=pk
    )
    sessions = event.event_sessions.select_related("user").order_by("start_time")

    user_registration = None
    if request.user.is_authenticated:
        user_registration = event.event_registrations.filter(user=request.user).first()

    return render(
        request,
        "events/detail.html",
        {"event": event, "sessions": sessions, "user_registration": user_registration},
    )


def session_detail(request, pk):
    """Mirrors EventSessionsController#show."""
    session = get_object_or_404(
        EventSession.objects.select_related("event", "user"), pk=pk
    )
    return render(request, "events/session_detail.html", {"session": session})


@login_required
def registration_new(request, event_id):
    """Mirrors EventRegistrationsController#new/#create. GET shows the
    form (or the relevant "not allowed" alert, ported from
    event_registrations/new.html.erb); POST creates the registration.
    """
    event = get_object_or_404(
        Event.objects.select_related("chapter", "venue", "event_type"), pk=event_id
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


def registration_index(request, event_id):
    """Mirrors EventRegistrationsController#index — avatar grid of
    visible registrations."""
    event = get_object_or_404(Event, pk=event_id)
    registrations = event.event_registrations.filter(visible=True).select_related("user")
    return render(
        request, "events/registration_index.html", {"event": event, "registrations": registrations}
    )
