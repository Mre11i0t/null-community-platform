from django.shortcuts import get_object_or_404, render

from .models import Page


def page_detail(request, slug):
    """Mirrors PagesController#show."""
    page = get_object_or_404(Page, slug=slug, published=True)
    return render(request, "content/page_detail.html", {"page": page})
