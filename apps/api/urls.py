"""API v2 — replaces the original Grape /api-v2 mounted API. See
doc/feature-document.md Part 5 for the original endpoint contract.
"""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from . import views

app_name = "api"

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="swagger"),
    path("chapters/", views.ChapterListView.as_view(), name="chapters"),
    path("events/", views.EventListView.as_view(), name="events"),
    path("events/<int:event_id>/event_sessions/", views.EventSessionListView.as_view(), name="event_sessions"),
    path(
        "events/<int:event_id>/event_registrations/",
        views.EventRegistrationListView.as_view(),
        name="event_registrations",
    ),
    path("authentications/password/", views.AuthenticatePasswordView.as_view(), name="authenticate_password"),
    path("users/me/", views.UserMeView.as_view(), name="user_me"),
    path("users/events/", views.UserEventsView.as_view(), name="user_events"),
    path("users/sessions/", views.UserSessionsView.as_view(), name="user_sessions"),
]
