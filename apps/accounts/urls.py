from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/<int:pk>/", views.public_profile, name="public_profile"),
    path("report-incident", views.report_incident, name="report_incident"),
    path("settings/delete-account", views.delete_account, name="delete_account"),
    path("settings/export.json", views.export_data, name="export_data"),
    path("settings/notifications", views.notification_preferences, name="notification_preferences"),
    path("settings/achievements/new", views.add_achievement, name="add_achievement"),
    path("settings/profile", views.profile_edit, name="profile_edit"),
    path("my_rsvps", views.my_rsvps, name="my_rsvps"),
]
