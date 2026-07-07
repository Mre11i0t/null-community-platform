from django.urls import path

from . import views

app_name = "chapters"

urlpatterns = [
    path("", views.list_chapters, name="list"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/calendar.ics", views.calendar_ics, name="calendar_ics"),
    path("<int:pk>/leaders", views.leaders_json, name="leaders_json"),
    path("<int:pk>/upcoming_events", views.upcoming_events_json, name="upcoming_events_json"),
]
