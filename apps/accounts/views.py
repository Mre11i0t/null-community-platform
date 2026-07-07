from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .models import User


def public_profile(request, pk):
    """Mirrors HomeController#public_profile."""
    user = get_object_or_404(User, pk=pk)
    speaker_sessions = user.speaker_sessions()
    # Rev 3: topics spoken on (tag cloud) + co-speaker credits
    topics = sorted({tag.name for session in speaker_sessions for tag in session.tags.all()})
    return render(
        request,
        "accounts/public_profile.html",
        {
            "profile_user": user,
            "speaker_sessions": speaker_sessions,
            "co_speaker_sessions": user.co_speaker_sessions.filter(deleted_at__isnull=True),
            "topics": topics,
            "registered_participation": user.registered_participation(),
            "achievements": user.achievements.all(),
        },
    )


@login_required
def report_incident(request):
    """Rev 3 trust & safety: confidential CoC incident report, emailed
    to the response team (INCIDENT_RESPONSE_ADDRESSES) and tracked in
    the admin. Login required to raise the cost of spam; the report
    itself is never shown publicly."""
    from django.conf import settings
    from django.core.mail import send_mail

    from apps.core.models import IncidentReport

    sent = False
    if request.method == "POST":
        description = request.POST.get("description", "").strip()
        if description:
            report = IncidentReport.objects.create(
                reporter=request.user,
                description=description,
                where=request.POST.get("where", "").strip()[:255],
                contact_ok=bool(request.POST.get("contact_ok")),
            )
            send_mail(
                subject=f"[null][CONFIDENTIAL] Incident report #{report.pk}",
                message=(
                    f"A new incident report was filed.\n\n"
                    f"Where: {report.where or '(not given)'}\n"
                    f"Reporter may be contacted: {'yes' if report.contact_ok else 'no'}\n\n"
                    f"{report.description}\n\n"
                    f"Triage: {settings.SITE_BASE_URL}/admin/core/incidentreport/{report.pk}/change/"
                ),
                from_email=None,
                recipient_list=settings.INCIDENT_RESPONSE_ADDRESSES,
                fail_silently=True,
            )
            sent = True
    return render(request, "accounts/report_incident.html", {"sent": sent})


@login_required
def delete_account(request):
    """Rev 3 (closes gap #1): self-service deletion with anonymization.
    Requires re-typing the password so a hijacked session can't nuke an
    account silently."""
    from django.contrib import messages
    from django.contrib.auth import logout
    from django.shortcuts import redirect

    error = None
    if request.method == "POST":
        if request.user.check_password(request.POST.get("password", "")):
            request.user.anonymize_and_deactivate()
            logout(request)
            messages.success(request, "Your account has been deleted. Take care!")
            return redirect("core:home")
        error = "Incorrect password."
    return render(request, "accounts/delete_account.html", {"error": error})


@login_required
def export_data(request):
    """Rev 3 DPDP/GDPR data portability: everything we hold about the
    member, as a JSON download."""
    from django.http import JsonResponse

    user = request.user
    payload = {
        "profile": {
            "email": user.email,
            "name": user.name,
            "handle": user.handle,
            "about_me": user.about_me,
            "homepage": user.homepage,
            "social": {
                "twitter": user.twitter_handle,
                "facebook": user.facebook_profile,
                "linkedin": user.linkedin_profile,
                "slideshare": user.slideshare_profile,
                "github": user.github_profile,
            },
            "joined": user.created_at.isoformat(),
        },
        "registrations": [
            {
                "event": r.event.name,
                "chapter": r.event.chapter.name,
                "date": r.event.start_time.isoformat(),
                "state": r.state,
                "checked_in_at": r.checked_in_at.isoformat() if r.checked_in_at else None,
                "custom_answers": r.custom_answers,
            }
            for r in user.event_registrations.select_related("event", "event__chapter")
        ],
        "sessions": [
            {"name": s.name, "event": s.event.name, "date": s.start_time.isoformat()}
            for s in user.event_sessions.all()
        ],
        "comments": [
            {"session": c.event_session.name, "body": c.comment_body, "at": c.created_at.isoformat()}
            for c in user.session_comments.select_related("event_session")
        ],
        "proposals": [
            {"topic": p.session_topic, "chapter": p.chapter.name, "status": p.status}
            for p in user.session_proposals.select_related("chapter")
        ],
        "achievements": [
            {"type": a.achievement_type, "info": a.info, "reference": a.reference}
            for a in user.achievements.all()
        ],
        "coc_acknowledgements": [
            {"version": ack.version, "at": ack.created_at.isoformat()}
            for ack in user.coc_acknowledgements.all()
        ],
    }
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = 'attachment; filename="my-null-data.json"'
    return response
