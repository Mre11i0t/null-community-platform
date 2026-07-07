def current_chapter(request):
    """Exposes the chapter whose site is being viewed (set by
    ChapterSiteMiddleware) to every template; None on the root site."""
    return {"current_chapter": getattr(request, "chapter", None)}
