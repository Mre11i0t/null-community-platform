from celery import shared_task
from django.core.mail import send_mail

from apps.chapters.models import Chapter

from . import services


@shared_task
def send_monthly_chapter_reports():
    """First-of-month summary email to every active chapter's leads —
    the numbers they'd otherwise have to go look up."""
    sent = 0
    for chapter in Chapter.active_chapters():
        leads = chapter.leads()
        recipients = [lead.email for lead in leads if lead.email]
        if not recipients:
            continue
        traffic = services.chapter_traffic(chapter, days=30)
        referrers = services.top_referrers(days=30, chapter=chapter, limit=5)
        health = services.chapter_health(chapter, days=30)
        speakers = services.speaker_stats(chapter, days=30)

        referrer_lines = "\n".join(
            f"  - {row['referrer_domain']}: {row['hits']}" for row in referrers
        ) or "  (none recorded)"
        body = (
            f"null {chapter.name} — last 30 days\n"
            f"{'=' * 40}\n\n"
            f"Site traffic: {traffic} page views\n"
            f"Top referrers:\n{referrer_lines}\n\n"
            f"Events held: {health['events']}\n"
            f"Registrations: {health['registrations']} "
            f"({health['unique_attendees']} unique, {health['new_members']} new members, "
            f"{health['repeat_rate']}% repeat rate)\n\n"
            f"Sessions: {speakers['sessions']} by {speakers['speakers']} speakers "
            f"({speakers['first_time_speakers']} first-time)\n"
            f"Past sessions missing slides: {speakers['missing_slides']}, "
            f"missing video: {speakers['missing_video']}\n"
        )
        send_mail(
            subject=f"[null] Monthly chapter report — {chapter.name}",
            message=body,
            from_email=None,
            recipient_list=recipients,
            fail_silently=True,
        )
        sent += 1
    return sent
