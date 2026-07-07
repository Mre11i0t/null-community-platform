from django.shortcuts import get_object_or_404, render

from .models import Page


def page_detail(request, slug):
    """Mirrors PagesController#show."""
    page = get_object_or_404(Page, slug=slug, published=True)
    return render(request, "content/page_detail.html", {"page": page})


def page_edit(request, slug):
    """Rev 3 parity: enforces PageAccessPermission — the original let
    admins grant ReadWrite on individual pages so a trusted non-admin
    could maintain them (e.g. a CoC editor). ReadOnly grants (and staff)
    may view unpublished drafts via this route; ReadWrite may edit."""
    from django.contrib import messages
    from django.contrib.auth.decorators import login_required as _lr
    from django.http import Http404
    from django.shortcuts import redirect

    from .models import PageAccessPermission

    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())

    page = get_object_or_404(Page, slug=slug)
    grants = set(
        PageAccessPermission.objects.filter(page=page, user=request.user).values_list(
            "permission_type", flat=True
        )
    )
    can_write = request.user.is_staff or PageAccessPermission.READ_WRITE in grants
    can_read = can_write or PageAccessPermission.READ_ONLY in grants
    if not can_read:
        raise Http404

    if request.method == "POST":
        if not can_write:
            raise Http404
        page.title = request.POST.get("title", page.title).strip()[:255]
        page.content = request.POST.get("content", page.content)
        page.save()
        messages.success(request, "Page updated.")
        return redirect("content:page_detail", slug=page.slug)

    return render(
        request, "content/page_edit.html", {"page": page, "can_write": can_write}
    )
