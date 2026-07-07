from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("events/", views.event_index, name="event_index"),
    path("events/<int:event_id>/check_in/", views.check_in_dashboard, name="check_in_dashboard"),
    path("events/<int:event_id>/check_in/scan/", views.check_in_scan, name="check_in_scan"),
    path("events/<int:event_id>/check_in/mark/", views.check_in_mark, name="check_in_mark"),
    path("events/<int:event_id>/check_in/stats.json", views.check_in_stats_json, name="check_in_stats_json"),
    path("events/<int:event_id>/kiosk/<str:token>/", views.kiosk, name="kiosk"),
    path("events/new/", views.event_new, name="event_new"),
    path("events/<int:pk>/", views.event_show, name="event_show"),
    path("events/<int:pk>/edit/", views.event_edit, name="event_edit"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("events/<int:event_id>/sessions/", views.session_index, name="session_index"),
    path("events/<int:event_id>/sessions/new/", views.session_new, name="session_new"),
    path("events/<int:event_id>/sessions/suggest_user/", views.session_suggest_user, name="session_suggest_user"),
    path("events/<int:event_id>/sessions/<int:pk>/", views.session_show, name="session_show"),
    path("events/<int:event_id>/sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("events/<int:event_id>/sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    path("events/<int:event_id>/registrations/", views.registration_index, name="registration_index"),
    path("events/<int:event_id>/registrations/approval/", views.approval_queue, name="approval_queue"),
    path(
        "events/<int:event_id>/registrations/approval/<int:pk>/",
        views.approval_decide,
        name="approval_decide",
    ),
    path(
        "events/<int:event_id>/registrations/export_csv/",
        views.registration_export_csv,
        name="registration_export_csv",
    ),
    path(
        "events/<int:event_id>/registrations/mass_update/",
        views.registration_mass_update,
        name="registration_mass_update",
    ),
    path("events/<int:event_id>/mailer_tasks/", views.mailer_task_index, name="mailer_task_index"),
    path("events/<int:event_id>/mailer_tasks/new/", views.mailer_task_new, name="mailer_task_new"),
    path("events/<int:event_id>/mailer_tasks/<int:pk>/", views.mailer_task_show, name="mailer_task_show"),
    path("events/<int:event_id>/mailer_tasks/<int:pk>/edit/", views.mailer_task_edit, name="mailer_task_edit"),
    path(
        "events/<int:event_id>/mailer_tasks/<int:pk>/execute/", views.mailer_task_execute, name="mailer_task_execute"
    ),
    path("venues/", views.venue_index, name="venue_index"),
    path("venues/new/", views.venue_new, name="venue_new"),
    path("venues/<int:pk>/", views.venue_show, name="venue_show"),
    path("venues/<int:pk>/edit/", views.venue_edit, name="venue_edit"),
    path("venues/<int:pk>/delete/", views.venue_delete, name="venue_delete"),
    path("chapters/", views.chapter_index, name="chapter_index"),
    path("chapters/<int:pk>/edit/", views.chapter_edit, name="chapter_edit"),
]
