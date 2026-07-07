from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("upcoming", views.upcoming, name="upcoming"),
    path("archives", views.archives, name="archives"),
    path("about", views.about, name="about"),
    path("privacy", views.privacy, name="privacy"),
    path("calendar", views.calendar, name="calendar"),
    path("start-a-chapter", views.start_chapter, name="start_chapter"),
    path("sessions/", views.session_search, name="session_search"),
    path("stats", views.stats_index, name="stats_index"),
    path("stats/<int:year>", views.stats_show, name="stats_show"),
]
