import csv
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.chapters.models import Chapter
from apps.events.models import Event, EventRegistration, EventSession, Venue
from apps.notifications.models import EventMailerTask

from .forms import (
    LeadChapterForm,
    LeadEventForm,
    LeadEventMailerTaskForm,
    LeadEventSessionForm,
    LeadVenueForm,
)


def require_leader(view_func):
    """Ported from ApplicationController#authorize_leader! — must manage
    at least one chapter."""

    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.managed_chapters().exists():
            raise PermissionDenied("You do not manage any chapters.")
        return view_func(request, *args, **kwargs)

    return wrapper


def _load_authorized_event(request, event_id):
    """Ported from Leads::*Controller#load_authorize_event! — authorize!
    :manage, @event (CanCan rule: user manages event's chapter)."""
    event = get_object_or_404(Event, pk=event_id)
    if not request.user.managed_chapter(event.chapter):
        raise PermissionDenied("You do not manage this event's chapter.")
    return event


# --- Events ---------------------------------------------------------------


@require_leader
def event_index(request):
    show_old = request.GET.get("show_old")
    events = request.user.managed_old_events() if show_old else request.user.managed_events()
    return render(request, "leads/events/index.html", {"events": events.order_by("start_time"), "show_old": show_old})


@require_leader
def event_show(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not request.user.managed_chapter(event.chapter):
        raise PermissionDenied
    return render(request, "leads/events/show.html", {"event": event})


@require_leader
def event_new(request):
    if request.method == "POST":
        form = LeadEventForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            event = form.save(commit=False)
            event.public = False
            event.save()
            messages.success(request, "Event created successfully.")
            return redirect("leads:event_show", pk=event.pk)
    else:
        form = LeadEventForm(user=request.user)
    return render(request, "leads/events/form.html", {"form": form, "is_edit": False})


@require_leader
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if not request.user.managed_chapter(event.chapter):
        raise PermissionDenied
    if request.method == "POST":
        form = LeadEventForm(request.POST, request.FILES, instance=event, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated successfully.")
            return redirect("leads:event_show", pk=event.pk)
    else:
        form = LeadEventForm(instance=event, user=request.user)
    return render(request, "leads/events/form.html", {"form": form, "is_edit": True, "event": event})


@require_leader
@require_POST
def event_delete(request, pk):
    """Ported from Leads::EventsController#destroy — deletion is
    disabled in the original (commented out), just redirects."""
    messages.warning(request, "Event deletion is currently disabled.")
    return redirect("leads:event_index")


# --- Event Sessions --------------------------------------------------------


@require_leader
def session_index(request, event_id):
    event = _load_authorized_event(request, event_id)
    sessions = event.event_sessions.select_related("user").order_by("start_time")
    return render(request, "leads/event_sessions/index.html", {"event": event, "sessions": sessions})


@require_leader
def session_new(request, event_id):
    event = _load_authorized_event(request, event_id)
    if request.method == "POST":
        form = LeadEventSessionForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save(commit=False)
            session.event = event
            session.save()
            messages.success(request, "Event session created successfully.")
            return redirect("leads:session_show", event_id=event.pk, pk=session.pk)
    else:
        form = LeadEventSessionForm()
    return render(request, "leads/event_sessions/form.html", {"event": event, "form": form, "is_edit": False})


@require_leader
def session_show(request, event_id, pk):
    event = _load_authorized_event(request, event_id)
    session = get_object_or_404(EventSession, pk=pk, event=event)
    return render(request, "leads/event_sessions/show.html", {"event": event, "session": session})


@require_leader
def session_edit(request, event_id, pk):
    event = _load_authorized_event(request, event_id)
    session = get_object_or_404(EventSession, pk=pk, event=event)
    if request.method == "POST":
        form = LeadEventSessionForm(request.POST, request.FILES, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, "Event session has been updated successfully.")
            return redirect("leads:session_show", event_id=event.pk, pk=session.pk)
    else:
        form = LeadEventSessionForm(instance=session)
    return render(
        request, "leads/event_sessions/form.html", {"event": event, "form": form, "is_edit": True, "session": session}
    )


@require_leader
@require_POST
def session_delete(request, event_id, pk):
    """Ported from Leads::EventSessionsController#destroy — disabled."""
    event = _load_authorized_event(request, event_id)
    messages.warning(request, "Session deletion disabled currently.")
    return redirect("leads:session_index", event_id=event.pk)


@require_leader
def session_suggest_user(request, event_id):
    """Ported from Leads::EventSessionsController#suggest_user."""
    _load_authorized_event(request, event_id)
    q = request.GET.get("q", "")
    users = User.objects.filter(name__icontains=q) | User.objects.filter(email__icontains=q)
    users = users[:5]
    return JsonResponse([{"id": u.pk, "name": u.name, "email": u.email} for u in users], safe=False)


# --- Venues -----------------------------------------------------------------


@require_leader
def venue_index(request):
    venues = request.user.managed_venues().order_by("created_at")
    return render(request, "leads/venues/index.html", {"venues": venues})


@require_leader
def venue_new(request):
    if request.method == "POST":
        form = LeadVenueForm(request.POST, user=request.user)
        if form.is_valid():
            venue = form.save(commit=False)
            if not request.user.managed_chapter(venue.chapter):
                raise PermissionDenied
            venue.save()
            messages.success(request, "Venue created successfully.")
            return redirect("leads:venue_show", pk=venue.pk)
    else:
        form = LeadVenueForm(user=request.user)
    return render(request, "leads/venues/form.html", {"form": form, "is_edit": False})


@require_leader
def venue_show(request, pk):
    venue = get_object_or_404(Venue, pk=pk)
    if not request.user.managed_venue(venue):
        raise PermissionDenied
    return render(request, "leads/venues/show.html", {"venue": venue})


@require_leader
def venue_edit(request, pk):
    venue = get_object_or_404(Venue, pk=pk)
    if not request.user.managed_venue(venue):
        raise PermissionDenied
    if request.method == "POST":
        form = LeadVenueForm(request.POST, instance=venue, user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            if not request.user.managed_chapter(updated.chapter):
                raise PermissionDenied
            updated.save()
            messages.success(request, "Venue updated successfully.")
            return redirect("leads:venue_show", pk=venue.pk)
    else:
        form = LeadVenueForm(instance=venue, user=request.user)
    return render(request, "leads/venues/form.html", {"form": form, "is_edit": True, "venue": venue})


@require_leader
@require_POST
def venue_delete(request, pk):
    """Ported from Leads::VenuesController#destroy — disabled."""
    venue = get_object_or_404(Venue, pk=pk)
    if not request.user.managed_venue(venue):
        raise PermissionDenied
    messages.warning(request, "Deletion is currently disabled.")
    return redirect("leads:venue_index")


# --- Event Registrations -----------------------------------------------------


@require_leader
def registration_index(request, event_id):
    event = _load_authorized_event(request, event_id)
    registrations = event.event_registrations.select_related("user").order_by("-created_at")
    return render(
        request,
        "leads/event_registrations/index.html",
        {"event": event, "registrations": registrations, "states": EventRegistration.STATE_CHOICES},
    )


@require_leader
def registration_export_csv(request, event_id):
    """Ported from Leads::EventRegistrationsController#export_csv."""
    event = _load_authorized_event(request, event_id)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f"attachment; filename=event_{event.pk}_registrations.csv"
    writer = csv.writer(response)
    writer.writerow(["#", "Name", "Email", "Registered On", "State"])
    for reg in event.event_registrations.select_related("user"):
        writer.writerow([reg.pk, reg.user.name, reg.user.email, reg.created_at, reg.state])
    return response


@require_leader
@require_POST
def registration_mass_update(request, event_id):
    """Ported from Leads::EventRegistrationsController#mass_update —
    original accepted a JSON body {event_registrations: [{id, state}]}
    via AJAX; same contract here."""
    event = _load_authorized_event(request, event_id)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"status": "FAILED", "errors": [{"error_message": "Invalid JSON body"}]}, status=400)

    errors = []
    for item in payload.get("event_registrations", []):
        try:
            registration = event.event_registrations.get(pk=item["id"])
            registration.set_state(item["state"])
        except Exception as exc:  # noqa: BLE001 — mirrors the original's broad rescue
            errors.append({"registration_id": item.get("id"), "error_message": str(exc)})

    if errors:
        return JsonResponse({"status": "FAILED", "errors": errors})
    return JsonResponse({"status": "OK"})


# --- Event Mailer Tasks -------------------------------------------------------


@require_leader
def mailer_task_index(request, event_id):
    event = _load_authorized_event(request, event_id)
    tasks = EventMailerTask.objects.filter(event=event).order_by("-created_at")
    return render(request, "leads/event_mailer_tasks/index.html", {"event": event, "tasks": tasks})


@require_leader
def mailer_task_show(request, event_id, pk):
    event = _load_authorized_event(request, event_id)
    task = get_object_or_404(EventMailerTask, pk=pk, event=event)
    return render(request, "leads/event_mailer_tasks/show.html", {"event": event, "task": task})


@require_leader
def mailer_task_new(request, event_id):
    event = _load_authorized_event(request, event_id)
    if request.method == "POST":
        form = LeadEventMailerTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.event = event
            task.save()
            messages.success(request, "Event Mailer Task created successfully.")
            return redirect("leads:mailer_task_show", event_id=event.pk, pk=task.pk)
    else:
        form = LeadEventMailerTaskForm()
    return render(request, "leads/event_mailer_tasks/form.html", {"event": event, "form": form, "is_edit": False})


@require_leader
def mailer_task_edit(request, event_id, pk):
    event = _load_authorized_event(request, event_id)
    task = get_object_or_404(EventMailerTask, pk=pk, event=event)
    if request.method == "POST":
        form = LeadEventMailerTaskForm(request.POST, instance=task)
        if form.is_valid():
            # Ported from the controller: force ready_for_delivery=False
            # and never let executed be edited, preventing accidental
            # re-delivery via the edit form.
            updated = form.save(commit=False)
            updated.ready_for_delivery = False
            updated.save()
            messages.success(request, "Event Mailer Task updated successfully.")
            return redirect("leads:mailer_task_show", event_id=event.pk, pk=task.pk)
    else:
        form = LeadEventMailerTaskForm(instance=task)
    return render(
        request, "leads/event_mailer_tasks/form.html", {"event": event, "form": form, "is_edit": True, "task": task}
    )


@require_leader
@require_POST
def mailer_task_execute(request, event_id, pk):
    """Ported from Leads::EventMailerTasksController#execute — flips
    ready_for_delivery so the Celery task (apps/notifications/tasks.py)
    picks it up. Actual delivery is still a TODO there (see task #17)."""
    event = _load_authorized_event(request, event_id)
    task = get_object_or_404(EventMailerTask, pk=pk, event=event)
    if not task.executed and not task.ready_for_delivery:
        task.ready_for_delivery = True
        task.save()
        messages.success(request, "Mailer task queued for delivery.")
    return redirect("leads:mailer_task_index", event_id=event.pk)


# --- Chapters -----------------------------------------------------------------


@require_leader
def chapter_index(request):
    chapters = request.user.managed_chapters()
    return render(request, "leads/chapters/index.html", {"chapters": chapters})


@require_leader
def chapter_edit(request, pk):
    chapter = get_object_or_404(Chapter, pk=pk)
    if not request.user.managed_chapter(chapter):
        raise PermissionDenied
    if request.method == "POST":
        form = LeadChapterForm(request.POST, request.FILES, instance=chapter)
        if form.is_valid():
            form.save()
            messages.success(request, "Chapter updated successfully.")
            return redirect("leads:chapter_index")
    else:
        form = LeadChapterForm(instance=chapter)
    return render(request, "leads/chapters/form.html", {"form": form, "chapter": chapter})
