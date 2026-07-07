from django.conf import settings
from django.http import Http404

from .models import Chapter


class ChapterSiteMiddleware:
    """Resolves which chapter site (if any) a request belongs to, from the
    Host header — PRD Part 0's multi-tenant model.

    Sets `request.chapter`:
      * ``None``     — the root/directory site (ROOT_DOMAIN itself, www,
                       or a plain IP / testserver during dev and tests)
      * ``Chapter``  — a chapter site, matched by ``<subdomain>.ROOT_DOMAIN``
                       or by an exact ``custom_domain``

    Unknown subdomains/domains 404 here so a stray wildcard hit can't
    render the root site under an arbitrary hostname (cache poisoning /
    SEO-dupe hygiene). Host *header* trust is still ALLOWED_HOSTS' job —
    this runs after Django's own host validation.
    """

    ROOT_ALIASES = {"www", "testserver", "127.0.0.1", "localhost"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.chapter = self._resolve(request)
        return self.get_response(request)

    def _resolve(self, request):
        host = request.get_host().split(":")[0].lower()
        root = settings.ROOT_DOMAIN

        if host == root or host in self.ROOT_ALIASES:
            return None

        if host.endswith("." + root):
            sub = host[: -(len(root) + 1)]
            if sub == "www":
                return None
            chapter = Chapter.objects.filter(subdomain=sub, active=True).first()
            if chapter is None:
                raise Http404(f"No active chapter at subdomain {sub!r}")
            return chapter

        chapter = Chapter.objects.filter(custom_domain=host, active=True).first()
        if chapter is None:
            raise Http404(f"No chapter site for host {host!r}")
        return chapter
