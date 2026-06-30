from django.urls import path

from . import views

app_name = "content"

urlpatterns = [
    path("pages/<slug:slug>/", views.page_detail, name="page_detail"),
]
