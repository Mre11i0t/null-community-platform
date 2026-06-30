from django.urls import path

from . import views

app_name = "chapters"

urlpatterns = [
    path("", views.list_chapters, name="list"),
    path("<int:pk>/", views.detail, name="detail"),
]
