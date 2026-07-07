from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, render

from .models import Chapter


def list_chapters(request):
    """Mirrors ChaptersController#index."""
    chapters = Chapter.objects.all().order_by("name")
    return render(request, "chapters/list.html", {"chapters": chapters})


def detail(request, pk):
    """Mirrors ChaptersController#show."""
    chapter = get_object_or_404(Chapter, pk=pk)
    return render(
        request,
        "chapters/detail.html",
        {
            "chapter": chapter,
            "upcoming_events": chapter.upcoming_events().order_by("start_time"),
            "past_events": chapter.past_events().order_by("-start_time"),
        },
    )


def domain_check(request):
    """Caddy's `on_demand_tls { ask ... }` gate. Caddy calls
    GET /domains/check?domain=<host> before issuing a certificate for a
    host it has no cert for; 200 = issue, anything else = refuse. This is
    what stops strangers pointing random domains at the server and minting
    certificates against our ACME account (rate-limit exhaustion abuse).

    Root domain and *.ROOT_DOMAIN are normally covered by the wildcard
    cert, but they're accepted here too so the setup degrades gracefully
    if the wildcard isn't configured.
    """
    domain = request.GET.get("domain", "").split(":")[0].lower().strip()
    if not domain:
        return HttpResponseNotFound("no domain given")

    root = settings.ROOT_DOMAIN
    if domain == root or domain == f"www.{root}":
        return HttpResponse("ok")
    if domain.endswith("." + root):
        sub = domain[: -(len(root) + 1)]
        if Chapter.objects.filter(subdomain=sub, active=True).exists():
            return HttpResponse("ok")
        return HttpResponseNotFound("unknown subdomain")
    if Chapter.objects.filter(custom_domain=domain, active=True).exists():
        return HttpResponse("ok")
    return HttpResponseNotFound("unknown domain")


def calendar_ics(request, pk):
    """Mirrors ChaptersController#calendar — an iCal feed of upcoming
    public events for this chapter (subscribable in Google/Apple Calendar)."""
    chapter = get_object_or_404(Chapter, pk=pk)
    return HttpResponse(
        chapter.upcoming_events_ics(),
        content_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="calendar.ics"'},
    )
