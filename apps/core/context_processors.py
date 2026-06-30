import random

from django.conf import settings


def site_config(request):
    """Exposes CFG_* settings to every template, mirroring the global
    constants (CFG_APP_TITLE etc.) available throughout the original
    Rails views via config/misc_config.
    """
    return {
        "CFG_APP_TITLE": settings.CFG_APP_TITLE,
        "CFG_APP_DESCRIPTION": settings.CFG_APP_DESCRIPTION,
        "CFG_GOOGLE_GROUPS_URL": settings.CFG_GOOGLE_GROUPS_URL,
        "CFG_VOLUNTEER_FORM_URL": settings.CFG_VOLUNTEER_FORM_URL,
    }


def nav_data(request):
    """The original layouts/_header.html.erb queried Chapter/Page
    directly inside the partial (`Chapter.active_chapters...shuffle[0...5]`,
    `Page.published.order(...)`). Replicated here as a context processor
    so every page's nav dropdowns match without each view repeating the
    query.
    """
    from apps.chapters.models import Chapter
    from apps.content.models import Page

    active_chapters = list(Chapter.active_chapters().order_by("name"))
    random.shuffle(active_chapters)

    return {
        "nav_chapters": active_chapters[:5],
        "nav_pages": Page.published_pages().order_by("title"),
    }
