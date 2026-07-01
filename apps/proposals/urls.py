from django.urls import path

from . import views

app_name = "proposals"

urlpatterns = [
    path("session_proposals/", views.proposal_index, name="proposal_index"),
    path("session_proposals/new/", views.proposal_new, name="proposal_new"),
    path("session_proposals/<int:pk>/", views.proposal_show, name="proposal_show"),
    path("session_proposals/<int:pk>/edit/", views.proposal_edit, name="proposal_edit"),
    path("session_requests/new/", views.request_new, name="request_new"),
    path("session_requests/<int:pk>/", views.request_show, name="request_show"),
]
