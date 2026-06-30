from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("profile/<int:pk>/", views.public_profile, name="public_profile"),
]
