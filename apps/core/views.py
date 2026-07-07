from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.chapters.models import Chapter
from apps.events.models import Event, EventType

from .stats import Stat


def home(request):
    """Mirrors HomeController#index — homepage with stats panels and
    the upcoming events list.

    NOTE: the original page also rendered a live Google-Maps chapter
    pin map (chapters/_chapter_map_loader + Chapter.geo_locations,
    which calls out to Geocoder). That requires a Maps API key and
    geocoding integration that isn't wired up yet, so it is
    intentionally left out here rather than faked — see task #9.
    """
    events = Event.objects.future_public_events().order_by("start_time")
    if request.chapter:
        events = events.filter(chapter=request.chapter)
    return render(
        request,
        "home/index.html",
        {"events": events, "active_chapters_count": Chapter.active_chapters().count()},
    )


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
