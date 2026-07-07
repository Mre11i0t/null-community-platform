from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.chapters.models import Chapter
from apps.events.models import Event, EventType

from .stats import Stat


def home(request):
    """Chapter host: the chapter's event homepage (mirrors the original
    HomeController#index, scoped). Root host: the Rev 3 directory —
    chapter grid + collective stats, deliberately NOT an event listing
    (PRD Part 0).

    NOTE: the original page also rendered a live Google-Maps chapter
    pin map (chapters/_chapter_map_loader + Chapter.geo_locations,
    which calls out to Geocoder). That requires a Maps API key and
    geocoding integration that isn't wired up yet, so it is
    intentionally left out here rather than faked — see task #9.
    """
    if request.chapter is None:
        return directory(request)
    events = Event.objects.future_public_events().filter(chapter=request.chapter).order_by("start_time")
    return render(
        request,
        "home/index.html",
        {"events": events, "active_chapters_count": Chapter.active_chapters().count()},
    )


def directory(request):
    """Root-site landing: every active chapter with its next event, and
    all-time collective stats across the community."""
    from django.db.models import Count

    from apps.events.models import EventRegistration, EventSession

    chapters = list(Chapter.active_chapters().order_by("name"))
    totals = {
        "chapters": len(chapters),
        "events": Event.objects.public_events().count(),
        "sessions": EventSession.objects.alive().filter(placeholder=False).count(),
        "speakers": EventSession.objects.alive()
        .filter(placeholder=False)
        .values("user_id")
        .distinct()
        .count(),
        "registrations": EventRegistration.objects.count(),
    }
    return render(request, "home/directory.html", {"chapters": chapters, "totals": totals})


def start_chapter(request):
    """Rev 3: "Start a Chapter" — info page + application form that
    lands in the platform admins' inbox."""
    from django.conf import settings
    from django.core.mail import send_mail

    sent = False
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        city = request.POST.get("city", "").strip()
        motivation = request.POST.get("motivation", "").strip()
        if name and email and city:
            send_mail(
                subject=f"[null] New chapter application — {city}",
                message=(
                    f"Name: {name}\nEmail: {email}\nCity: {city}\n\n"
                    f"Why they want to start a chapter:\n{motivation}"
                ),
                from_email=None,
                recipient_list=settings.NOTIFICATION_ADMIN_EVENT_CREATE,
                fail_silently=True,
            )
            sent = True
    return render(request, "home/start_chapter.html", {"sent": sent})


def session_search(request):
    """Root-site global session archive search (Rev 3): the cross-
    chapter view of every delivered talk, filterable by text or tag."""
    from django.core.paginator import Paginator as _Paginator

    from apps.events.models import EventSession

    q = (request.GET.get("q") or "").strip()
    sessions = (
        EventSession.objects.alive()
        .filter(placeholder=False, event__public=True)
        .select_related("event", "event__chapter", "user")
        .order_by("-start_time")
    )
    if q:
        from django.db.models import Q as _Q

        sessions = sessions.filter(
            _Q(name__icontains=q) | _Q(description__icontains=q) | _Q(tags__name__icontains=q)
        ).distinct()
    page_obj = _Paginator(sessions, 25).get_page(request.GET.get("page"))
    return render(request, "home/session_search.html", {"page_obj": page_obj, "q": q})


def upcoming(request):
    """Mirrors HomeController#upcoming."""
    events = Event.objects.future_public_events().order_by("start_time")
    if request.chapter:
        events = events.filter(chapter=request.chapter)
    return render(request, "home/upcoming.html", {"events": events})


def archives(request):
    """Mirrors HomeController#archives — paginated past events."""
    events_qs = Event.objects.archives().order_by("-start_time")
    if request.chapter:
        events_qs = events_qs.filter(chapter=request.chapter)
    paginator = Paginator(events_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "home/archives.html", {"page_obj": page_obj, "events": page_obj.object_list})


def about(request):
    return render(request, "home/about.html")


def privacy(request):
    return render(request, "home/privacy.html")


def calendar(request):
    """Mirrors HomeController#calendar — an embedded read-only public
    Google Calendar (not an ICS feed; see Chapter#calendar_ics for that)."""
    return render(request, "home/calendar.html")


def stats_index(request):
    """Mirrors StatsController#index — redirects to last year's stats."""
    return redirect(reverse("core:stats_show", args=[timezone.now().year - 1]))


def stats_show(request, year):
    """Mirrors StatsController#show + the `_data_view` partial (event
    counts by type, participation, unique speakers, speaker leaderboard).

    The original also had a `_graph_view` tab (timeline + pie chart via
    `google.load("visualization", ...)`), which depends on Google's
    "Google JSAPI" loader — a service Google shut down years ago, so
    that tab has been broken in the original app itself for a long
    time. Not ported for that reason, not out of scope-cutting.
    """
    chapter = None
    chapter_id = request.GET.get("chapter_id")
    if chapter_id and chapter_id != "ALL":
        chapter = get_object_or_404(Chapter, pk=chapter_id)

    stat = Stat(year, chapter)
    events = stat.events()
    event_sessions = stat.event_sessions()
    event_type_rows = [
        {
            "event_type": event_type,
            "event_count": events.filter(event_type=event_type).count(),
            "session_count": event_sessions.filter(event__event_type=event_type).count(),
        }
        for event_type in EventType.objects.order_by("name")
    ]
    return render(
        request,
        "stats/show.html",
        {
            "stat": stat,
            "year": year,
            "chapter": chapter,
            "chapters": Chapter.objects.order_by("name"),
            "event_type_rows": event_type_rows,
            "top_speakers": stat.top_speakers(100000),
            "years": range(timezone.now().year, 2009, -1),
        },
    )


def _abs(request, path):
    return f"{request.scheme}://{request.get_host()}{path}"


def sitemap_xml(request):
    """Rev 3 chapter-scoped SEO: each chapter site serves a sitemap of
    ITS OWN events/sessions/pages (so delhi.null.community ranks for
    Delhi), while the root site maps the directory-level pages. Hand-
    rolled rather than django.contrib.sitemaps because the sites
    framework assumes one canonical domain — we have one per chapter."""
    from django.http import HttpResponse

    from apps.content.models import Page
    from apps.events.models import EventSession

    urls = [(_abs(request, "/"), "daily")]
    chapter = request.chapter

    if chapter:
        events = Event.objects.public_events().filter(chapter=chapter)
        sessions = EventSession.objects.alive().filter(
            event__chapter=chapter, event__public=True, placeholder=False
        )
        urls += [(_abs(request, "/upcoming"), "daily"), (_abs(request, "/archives"), "weekly")]
    else:
        events = Event.objects.public_events()
        sessions = EventSession.objects.alive().filter(event__public=True, placeholder=False)
        urls += [
            (_abs(request, "/chapters/"), "weekly"),
            (_abs(request, "/stats"), "monthly"),
            (_abs(request, "/about"), "monthly"),
        ]

    urls += [(_abs(request, e.get_absolute_url()), "weekly") for e in events]
    urls += [(_abs(request, s.get_absolute_url()), "monthly") for s in sessions]
    urls += [
        (_abs(request, f"/pages/{page.slug}"), "monthly")
        for page in Page.published_pages()
    ]

    body = ['<?xml version="1.0" encoding="UTF-8"?>']
    body.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for loc, freq in urls:
        body.append(f"<url><loc>{loc}</loc><changefreq>{freq}</changefreq></url>")
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml")


def robots_txt(request):
    from django.http import HttpResponse

    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /leads/",
        "Disallow: /accounts/",
        f"Sitemap: {_abs(request, '/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
