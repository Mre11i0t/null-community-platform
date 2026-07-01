from django.http import HttpResponse
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


def calendar_ics(request, pk):
    """Mirrors ChaptersController#calendar — an iCal feed of upcoming
    public events for this chapter (subscribable in Google/Apple Calendar)."""
    chapter = get_object_or_404(Chapter, pk=pk)
    return HttpResponse(
        chapter.upcoming_events_ics(),
        content_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="calendar.ics"'},
    )
