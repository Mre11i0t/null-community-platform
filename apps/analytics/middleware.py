from urllib.parse import urlsplit

from .models import PageVisit

# Paths that are noise for traffic attribution.
SKIP_PREFIXES = (
    "/static/",
    "/media/",
    "/admin/",
    "/__debug__/",
    "/domains/check",
    "/api-v2/",
    "/favicon",
)

# Self-referrals (navigation within our own sites) don't count as a source.
_BOT_MARKERS = ("bot", "crawler", "spider", "slurp", "curl", "wget", "python-requests")


class PageVisitMiddleware:
    """Logs one row per page view, after the response (so a 404/500
    doesn't pollute stats and logging can never break the page). Runs
    after ChapterSiteMiddleware so request.chapter is attribution-ready."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._record(request, response)
        except Exception:  # never let analytics take a page down
            pass
        return response

    def _record(self, request, response):
        if request.method != "GET" or response.status_code != 200:
            return
        if "text/html" not in response.get("Content-Type", ""):
            return
        path = request.path
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return
        user_agent = request.headers.get("User-Agent", "").lower()
        if any(marker in user_agent for marker in _BOT_MARKERS):
            return

        host = request.get_host().split(":")[0].lower()
        referrer_domain = ""
        referrer = request.headers.get("Referer", "")
        if referrer:
            ref_host = urlsplit(referrer).hostname or ""
            # internal navigation isn't a traffic source
            if ref_host and ref_host.split(":")[0].lower() != host:
                referrer_domain = ref_host[:255]

        PageVisit.objects.create(
            host=host[:255],
            path=path[:255],
            chapter=getattr(request, "chapter", None),
            referrer_domain=referrer_domain,
            utm_source=request.GET.get("utm_source", "")[:64],
            utm_medium=request.GET.get("utm_medium", "")[:64],
            utm_campaign=request.GET.get("utm_campaign", "")[:64],
        )
