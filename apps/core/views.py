from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from apps.chapters.models import Chapter
from apps.events.models import Event


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
    return render(
        request,
        "home/index.html",
        {"events": events, "active_chapters_count": Chapter.active_chapters().count()},
    )


def upcoming(request):
    """Mirrors HomeController#upcoming."""
    events = Event.objects.future_public_events().order_by("start_time")
    return render(request, "home/upcoming.html", {"events": events})


def archives(request):
    """Mirrors HomeController#archives — paginated past events."""
    events_qs = Event.objects.archives().order_by("-start_time")
    paginator = Paginator(events_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "home/archives.html", {"page_obj": page_obj, "events": page_obj.object_list})


def about(request):
    return render(request, "home/about.html")


def privacy(request):
    return render(request, "home/privacy.html")
