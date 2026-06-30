"""API v2 — replaces the original Grape /api-v2 mounted API.

STATUS: schema/docs endpoints are wired up; resource endpoints
(chapters, events, event_sessions, event_registrations, users/me,
authentications/password) are scaffolded in serializers.py/views.py
but not yet implemented. See doc/feature-document.md Part 5 for the
full original endpoint contract this needs to satisfy.
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

app_name = "api"

urlpatterns = [
    path("", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger"),
]
