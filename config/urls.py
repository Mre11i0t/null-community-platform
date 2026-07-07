from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.chapters import views as chapter_views
from apps.events import views as event_views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Caddy on-demand-TLS gate — must stay cheap and unauthenticated.
    path("domains/check", chapter_views.domain_check, name="domain_check"),
    path("accounts/", include("allauth.urls")),
    path("api-v2/", include("apps.api.urls")),
    path("chapters/", include("apps.chapters.urls")),
    path("events/", include("apps.events.urls")),
    path("leads/", include("apps.leads.urls")),
    # Top-level to match the original's flat /venues/:id route (VenuesController#show).
    path("venues/<int:pk>/", event_views.venue_detail, name="venue_detail"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.proposals.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
