from django.shortcuts import render

from apps.events.models import Event
from apps.leads.views import require_leader

from . import services


@require_leader
def dashboard(request):
    """Chapter analytics for leads: traffic per domain + referrers,
    health vitals, speaker stats, and recent-event funnels. Admin/staff
    additionally see the all-domains traffic table."""
    chapters = request.user.managed_chapters()
    days = int(request.GET.get("days", 30) or 30)

    chapter_cards = []
    for chapter in chapters:
        recent_events = (
            Event.objects.alive().filter(chapter=chapter).order_by("-start_time")[:5]
        )
        chapter_cards.append(
            {
                "chapter": chapter,
                "traffic": services.chapter_traffic(chapter, days=days),
                "referrers": services.top_referrers(days=days, chapter=chapter, limit=8),
                "health": services.chapter_health(chapter),
                "speakers": services.speaker_stats(chapter),
                "funnels": [
                    {"event": event, **services.attendance_funnel(event)} for event in recent_events
                ],
            }
        )

    return render(
        request,
        "analytics/dashboard.html",
        {
            "chapter_cards": chapter_cards,
            "days": days,
            "traffic_by_host": services.traffic_by_host(days=days) if request.user.is_staff else None,
        },
    )
