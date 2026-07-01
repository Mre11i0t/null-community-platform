from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api-v2/schema/", include("apps.api.urls")),
    path("chapters/", include("apps.chapters.urls")),
    path("events/", include("apps.events.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.proposals.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
