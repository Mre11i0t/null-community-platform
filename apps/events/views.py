from django.shortcuts import get_object_or_404, render

from .models import Event, EventSession


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
