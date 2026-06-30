from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("<int:pk>/", views.detail, name="detail"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
]
