from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("<int:pk>/", views.detail, name="detail"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("<int:event_id>/registrations/new/", views.registration_new, name="registration_new"),
    path("<int:event_id>/registrations/<int:pk>/cancel/", views.registration_destroy, name="registration_destroy"),
    path("<int:event_id>/registrations/", views.registration_index, name="registration_index"),
]
