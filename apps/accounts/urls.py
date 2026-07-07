from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/<int:pk>/", views.public_profile, name="public_profile"),
    path("report-incident", views.report_incident, name="report_incident"),
    path("settings/delete-account", views.delete_account, name="delete_account"),
    path("settings/export.json", views.export_data, name="export_data"),
]
