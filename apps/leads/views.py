import csv
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.chapters.models import Chapter
from apps.events.models import Event, EventRegistration, EventSession, Venue
from apps.notifications.models import EventMailerTask
from apps.notifications.tasks import send_event_mailer_task

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
    """The original disabled destroy outright (gap #2); Rev 3 replaces it
    with soft-delete — the event vanishes from all public/lead listings
    but stays restorable in the admin."""
    event = _load_authorized_event(request, pk)
    event.soft_delete()
    messages.success(request, f'Event "{event.name}" has been archived.')
    return redirect("leads:event_index")


# --- Event Sessions --------------------------------------------------------


@require_leader
def session_index(request, event_id):
    event = _load_authorized_event(request, event_id)
    sessions = event.event_sessions.alive().select_related("user").order_by("start_time")
    return render(request, "leads/event_sessions/index.html", {"event": event, "sessions": sessions})


@require_leader
def session_new(request, event_id):
    event = _load_authorized_event(request, event_id)
    if request.method == "POST":
        form = LeadEventSessionForm(request.POST, request.FILES)
        form.instance.event = event
        if form.is_valid():
            session = form.save()
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
    """Soft-deletes a session (was disabled in the original — gap #2)."""
    event = _load_authorized_event(request, event_id)
    session = get_object_or_404(EventSession, pk=pk, event=event)
    session.soft_delete()
    messages.success(request, f'Session "{session.name}" has been archived.')
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
    """Soft-deletes a venue (was disabled in the original — gap #2).
    Blocked while any live event still uses it, since Event.venue is
    PROTECT and a hidden venue under a visible event would be confusing."""
    venue = get_object_or_404(Venue, pk=pk)
    if not request.user.managed_venue(venue):
        raise PermissionDenied
    if venue.events.alive().filter(end_time__gt=timezone.now()).exists():
        messages.warning(request, "This venue still has upcoming events — move or archive them first.")
        return redirect("leads:venue_index")
    venue.soft_delete()
    messages.success(request, f'Venue "{venue.name}" has been archived.')
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
    question_labels = [q["label"] for q in event.custom_questions]
    writer.writerow(["#", "Name", "Email", "Registered On", "State", "Checked In At"] + question_labels)
    for reg in event.event_registrations.select_related("user"):
        writer.writerow(
            [reg.pk, reg.user.name, reg.user.email, reg.created_at, reg.state, reg.checked_in_at or ""]
            + [reg.custom_answers.get(label, "") for label in question_labels]
        )
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
    ready_for_delivery and dispatches the Celery task that sends the mail
    (apps/notifications/tasks.py:send_event_mailer_task). Synchronous in
    dev via CELERY_TASK_ALWAYS_EAGER."""
    event = _load_authorized_event(request, event_id)
    task = get_object_or_404(EventMailerTask, pk=pk, event=event)
    if not task.executed and not task.ready_for_delivery:
        task.ready_for_delivery = True
        task.save()
        send_event_mailer_task.delay(task.pk)
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


# --- Check-in (Rev 3 — per-event opt-in) -------------------------------------


def _require_check_in(event):
    from django.http import Http404

    if not event.check_in_enabled:
        raise Http404("Check-in is not enabled for this event.")


@require_leader
def check_in_dashboard(request, event_id):
    """Live confirmed-vs-checked-in counts + kiosk link. The page polls
    the JSON endpoint below; no websockets needed at meetup scale."""
    from django.core import signing

    event = _load_authorized_event(request, event_id)
    _require_check_in(event)
    kiosk_token = signing.dumps({"event": event.pk}, salt="event-kiosk")
    return render(
        request,
        "leads/check_in/dashboard.html",
        {"event": event, "kiosk_token": kiosk_token, "stats": _check_in_stats(event)},
    )


def _check_in_stats(event):
    registrations = event.event_registrations
    return {
        "confirmed": registrations.filter(state=EventRegistration.STATE_CONFIRMED).count(),
        "checked_in": registrations.filter(checked_in_at__isnull=False).count(),
        "provisional": registrations.filter(state=EventRegistration.STATE_PROVISIONAL).count(),
    }


@require_leader
def check_in_stats_json(request, event_id):
    event = _load_authorized_event(request, event_id)
    _require_check_in(event)
    return JsonResponse(_check_in_stats(event))


@require_leader
def check_in_scan(request, event_id):
    """Scanner page: camera QR scanning (vendored html5-qrcode) with a
    manual code-entry fallback (also covers USB barcode scanners, which
    type the code and press Enter)."""
    event = _load_authorized_event(request, event_id)
    _require_check_in(event)
    return render(request, "leads/check_in/scan.html", {"event": event})


@require_leader
@require_POST
def check_in_mark(request, event_id):
    """Marks one registration checked-in, by QR/manual code or by
    registration id (from the kiosk/dashboard lists). JSON response so
    the scanner can stay on the page."""
    event = _load_authorized_event(request, event_id)
    _require_check_in(event)
    return _mark_checked_in(event, request.POST)


def _mark_checked_in(event, data):
    code = (data.get("code") or "").strip()
    reg_id = data.get("registration_id")
    if code:
        registration = event.event_registrations.filter(check_in_code=code).first()
    elif reg_id:
        registration = event.event_registrations.filter(pk=reg_id).first()
    else:
        return JsonResponse({"ok": False, "error": "No code given."}, status=400)

    if registration is None:
        return JsonResponse({"ok": False, "error": "Unknown code for this event."}, status=404)
    already = registration.checked_in_at is not None
    registration.check_in()
    return JsonResponse(
        {
            "ok": True,
            "name": registration.user.name or registration.user.email,
            "already_checked_in": already,
            "checked_in_at": registration.checked_in_at.isoformat(),
        }
    )


def kiosk(request, event_id, token):
    """Self-check-in kiosk: a tablet at the door, no login. Access is a
    signed token minted on the dashboard (valid 24h) so handing the URL
    to a volunteer's device never exposes a lead session. Locked down:
    search-by-name + mark-present only."""
    from django.core import signing
    from django.http import Http404

    event = get_object_or_404(Event, pk=event_id)
    _require_check_in(event)
    try:
        payload = signing.loads(token, salt="event-kiosk", max_age=60 * 60 * 24)
    except signing.BadSignature:
        raise Http404
    if payload.get("event") != event.pk:
        raise Http404

    if request.method == "POST":
        registration = event.event_registrations.filter(
            pk=request.POST.get("registration_id")
        ).first()
        if registration:
            registration.check_in()
            messages.success(request, "You're checked in — welcome!")
        return redirect("leads:kiosk", event_id=event.pk, token=token)

    q = (request.GET.get("q") or "").strip()
    results = []
    if len(q) >= 2:
        results = (
            event.event_registrations.select_related("user")
            .filter(Q(user__name__icontains=q) | Q(user__email__icontains=q))
            .order_by("user__name")[:20]
        )
    return render(
        request,
        "leads/check_in/kiosk.html",
        {"event": event, "q": q, "results": results, "token": token},
    )


# --- Approval queue (Rev 3 — closes gap #3) ----------------------------------


@require_leader
def approval_queue(request, event_id):
    """Dedicated review UI for provisional RSVPs on invite-only events —
    replaces abusing the generic mass-update flow (original gap #3).
    Shows each pending registration with its custom-question answers."""
    event = _load_authorized_event(request, event_id)
    pending = (
        event.event_registrations.filter(state=EventRegistration.STATE_PROVISIONAL)
        .select_related("user")
        .order_by("created_at")
    )
    return render(
        request,
        "leads/event_registrations/approval_queue.html",
        {"event": event, "pending": pending},
    )


@require_leader
@require_POST
def approval_decide(request, event_id, pk):
    from django.core.mail import send_mail

    event = _load_authorized_event(request, event_id)
    registration = get_object_or_404(
        EventRegistration, pk=pk, event=event, state=EventRegistration.STATE_PROVISIONAL
    )
    decision = request.POST.get("decision")
    note = (request.POST.get("note") or "").strip()[:255]

    if decision == "approve":
        registration.review_note = note
        registration.save(update_fields=["review_note", "updated_at"])
        registration.set_state(EventRegistration.STATE_CONFIRMED)
        subject = f"[null] Registration confirmed — {event.name}"
        body = (
            f"Your registration for {event.descriptive_name()} has been approved.\n\n"
            f"See you there! Event details: {settings.SITE_BASE_URL}{event.get_absolute_url()}"
        )
        messages.success(request, f"{registration.user} confirmed.")
    elif decision == "reject":
        registration.review_note = note
        registration.save(update_fields=["review_note", "updated_at"])
        registration.set_state(EventRegistration.STATE_NOT_ATTENDING)
        subject = f"[null] Registration update — {event.name}"
        body = (
            f"Unfortunately your registration for {event.descriptive_name()} was not "
            f"approved this time." + (f"\n\nNote from the organizers: {note}" if note else "")
        )
        messages.info(request, f"{registration.user} rejected.")
    else:
        messages.error(request, "Unknown decision.")
        return redirect("leads:approval_queue", event_id=event.pk)

    send_mail(subject, body, None, [registration.user.email], fail_silently=True)
    return redirect("leads:approval_queue", event_id=event.pk)


# --- CFP review pipeline (Rev 3 — closes gap #6) ------------------------------


@require_leader
def proposal_index(request):
    """All proposals for the leader's chapters, grouped by pipeline status."""
    from apps.proposals.models import SessionProposal

    status = request.GET.get("status", "")
    proposals = (
        SessionProposal.objects.filter(chapter__in=request.user.managed_chapters())
        .select_related("user", "chapter", "event_type")
        .order_by("-created_at")
    )
    if status:
        proposals = proposals.filter(status=status)
    return render(
        request,
        "leads/proposals/index.html",
        {
            "proposals": proposals,
            "status": status,
            "statuses": SessionProposal.STATUS_CHOICES,
        },
    )


@require_leader
def proposal_review(request, pk):
    """Proposal detail for reviewers: everyone's scores/comments, your
    own review form, and the status transition buttons."""
    from apps.proposals.models import ProposalReview, SessionProposal

    proposal = get_object_or_404(
        SessionProposal.objects.select_related("user", "chapter", "event_type"), pk=pk
    )
    if not request.user.managed_chapter(proposal.chapter):
        raise PermissionDenied

    my_review = proposal.reviews.filter(reviewer=request.user).first()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "review":
            score = int(request.POST.get("score", 0))
            if 1 <= score <= 5:
                ProposalReview.objects.update_or_create(
                    proposal=proposal,
                    reviewer=request.user,
                    defaults={"score": score, "comment": request.POST.get("comment", "").strip()},
                )
                if proposal.status == SessionProposal.STATUS_SUBMITTED:
                    proposal.set_status(SessionProposal.STATUS_UNDER_REVIEW)
                messages.success(request, "Review saved.")
            else:
                messages.error(request, "Score must be between 1 and 5.")
        elif action == "status":
            new_status = request.POST.get("status")
            try:
                proposal.set_status(new_status, note=request.POST.get("note", "").strip())
                messages.success(request, f"Proposal marked {proposal.get_status_display()} — proposer emailed.")
            except ValueError:
                messages.error(request, "Unknown status.")
        return redirect("leads:proposal_review", pk=proposal.pk)

    return render(
        request,
        "leads/proposals/review.html",
        {
            "proposal": proposal,
            "reviews": proposal.reviews.select_related("reviewer").order_by("-updated_at"),
            "my_review": my_review,
            "statuses": SessionProposal.STATUS_CHOICES,
        },
    )


@require_leader
def speaker_search(request):
    """Find past speakers by topic tag or name — feeds CFP curation."""
    q = (request.GET.get("q") or "").strip()
    speakers = []
    if q:
        speakers = (
            User.objects.filter(
                Q(event_sessions__tags__name__icontains=q)
                | Q(event_sessions__name__icontains=q)
                | Q(name__icontains=q)
            )
            .filter(event_sessions__placeholder=False, event_sessions__deleted_at__isnull=True)
            .distinct()[:50]
        )
    return render(request, "leads/proposals/speaker_search.html", {"q": q, "speakers": speakers})


@require_leader
@require_POST
def mailer_task_test_send(request, event_id, pk):
    """Rev 3: deliver the composed mailer to the lead themself, so the
    real thing never goes out with broken markdown or a typo'd link."""
    import markdown as md
    from django.core.mail import EmailMultiAlternatives

    event = _load_authorized_event(request, event_id)
    task = get_object_or_404(EventMailerTask, pk=pk, event=event)
    message = EmailMultiAlternatives(
        subject=f"[TEST] {task.subject}",
        body=task.body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[request.user.email],
    )
    message.attach_alternative(md.markdown(task.body, extensions=["fenced_code", "nl2br"]), "text/html")
    message.send()
    messages.success(request, f"Test email sent to {request.user.email}.")
    return redirect("leads:mailer_task_show", event_id=event.pk, pk=task.pk)


# --- Webhooks (Rev 3) --------------------------------------------------------


@require_leader
def webhook_index(request):
    from apps.notifications.models import WebhookDelivery, WebhookEndpoint

    chapters = request.user.managed_chapters()
    endpoints = WebhookEndpoint.objects.filter(chapter__in=chapters).select_related("chapter")

    if request.method == "POST":
        url = (request.POST.get("url") or "").strip()
        chapter = chapters.filter(pk=request.POST.get("chapter")).first()
        if url.startswith("https://") and chapter:
            endpoint = WebhookEndpoint.objects.create(chapter=chapter, url=url)
            messages.success(
                request,
                f"Endpoint added. Signing secret (save it now): {endpoint.secret}",
            )
        else:
            messages.error(request, "Endpoint must be https:// and belong to your chapter.")
        return redirect("leads:webhook_index")

    deliveries = WebhookDelivery.objects.filter(endpoint__in=endpoints).order_by("-created_at")[:30]
    return render(
        request,
        "leads/webhooks/index.html",
        {"endpoints": endpoints, "chapters": chapters, "deliveries": deliveries},
    )


@require_leader
@require_POST
def webhook_delete(request, pk):
    from apps.notifications.models import WebhookEndpoint

    endpoint = get_object_or_404(WebhookEndpoint, pk=pk)
    if not request.user.managed_chapter(endpoint.chapter):
        raise PermissionDenied
    endpoint.delete()
    messages.success(request, "Endpoint removed.")
    return redirect("leads:webhook_index")


# --- Event types (Rev 3 — closes gap #7) --------------------------------------


@require_leader
def event_type_index(request):
    """Leads can now see and create event types without pinging an
    admin (original gap #7). Editing/deleting stays admin-only since
    types are shared across every chapter."""
    from apps.events.models import EventType

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if name and not EventType.objects.filter(name__iexact=name).exists():
            EventType.objects.create(
                name=name,
                description=request.POST.get("description", "").strip(),
                max_participant=int(request.POST.get("max_participant") or 10000),
                public=bool(request.POST.get("public")),
                registration_required=bool(request.POST.get("registration_required")),
                invitation_required=bool(request.POST.get("invitation_required")),
            )
            messages.success(request, f'Event type "{name}" created.')
        else:
            messages.error(request, "Name is required and must be unique.")
        return redirect("leads:event_type_index")

    return render(
        request,
        "leads/event_types/index.html",
        {"event_types": EventType.objects.order_by("name")},
    )


# --- Notification run log (Rev 3 — closes gap #10) -----------------------------


@require_leader
def notification_log(request):
    """Read-only view of the notification machinery for the leader's
    chapters — replaces squinting at the admin-only Resque dashboard
    (original gap #10)."""
    from apps.notifications.models import EventAutomaticNotificationTask

    chapters = request.user.managed_chapters()
    auto_tasks = (
        EventAutomaticNotificationTask.objects.filter(event__chapter__in=chapters)
        .select_related("event")
        .order_by("-created_at")[:100]
    )
    mailer_tasks = (
        EventMailerTask.objects.filter(event__chapter__in=chapters)
        .select_related("event")
        .order_by("-created_at")[:50]
    )
    return render(
        request,
        "leads/notifications/log.html",
        {"auto_tasks": auto_tasks, "mailer_tasks": mailer_tasks},
    )
