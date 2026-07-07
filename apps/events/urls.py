from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/calendar.ics", views.event_ics, name="event_ics"),
    path("<int:event_id>/feedback/", views.event_feedback, name="event_feedback"),
    path("sessions/my_sessions/", views.my_sessions, name="my_sessions"),
    path("sessions/my_schedule/", views.my_schedule, name="my_schedule"),
    path("sessions/my_schedule.ics", views.my_schedule_ics, name="my_schedule_ics"),
    path("sessions/<int:pk>/star/", views.session_star, name="session_star"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/confirm/", views.session_confirm, name="session_confirm"),
    path("sessions/<int:pk>/like/", views.session_like, name="session_like"),
    path("sessions/<int:pk>/dislike/", views.session_dislike, name="session_dislike"),
    path("sessions/<int:session_id>/comments/new/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/edit/", views.comment_update, name="comment_update"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
    path("<int:event_id>/registrations/new/", views.registration_new, name="registration_new"),
    path("<int:event_id>/registrations/<int:pk>/cancel/", views.registration_destroy, name="registration_destroy"),
    path("<int:event_id>/registrations/", views.registration_index, name="registration_index"),
    path("<int:event_id>/registrations/<int:pk>/qr.png", views.registration_qr, name="registration_qr"),
]
