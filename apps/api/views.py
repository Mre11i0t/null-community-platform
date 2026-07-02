from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserApiToken
from apps.chapters.models import Chapter
from apps.events.models import Event, EventRegistration, EventSession

from .serializers import (
    ChapterSerializer,
    EventRegistrationSerializer,
    EventSerializer,
    EventSessionSerializer,
    UserMeSerializer,
)


class ChapterListView(generics.ListAPIView):
    """Mirrors API::Chapters#index — GET /chapters?all=true."""

    serializer_class = ChapterSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        if self.request.query_params.get("all"):
            return Chapter.objects.all()
        return Chapter.active_chapters()


class EventListView(generics.ListAPIView):
    """Mirrors API::Events#index — GET /events?all=true&page=&per_page=."""

    serializer_class = EventSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        if self.request.query_params.get("all"):
            return Event.objects.public_events().order_by("start_time")
        return Event.objects.future_public_events().order_by("start_time")


class EventSessionListView(generics.ListAPIView):
    """Mirrors API::EventSession#index — GET /events/:event_id/event_sessions."""

    serializer_class = EventSessionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        event = Event.objects.public_events().filter(pk=self.kwargs["event_id"]).first()
        return event.event_sessions.order_by("start_time") if event else EventSession.objects.none()


class EventRegistrationListView(generics.ListAPIView):
    """Mirrors API::EventRegistration#index — GET /events/:event_id/event_registrations."""

    serializer_class = EventRegistrationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        event = Event.objects.public_events().filter(pk=self.kwargs["event_id"]).first()
        if not event:
            return EventRegistration.objects.none()
        return event.event_registrations.filter(visible=True).select_related("user").order_by("-created_at")


class AuthenticatePasswordView(APIView):
    """Mirrors API::Authentications#password — POST /authentications/password."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        client_name = request.data.get("client_name")
        if not all([email, password, client_name]):
            return Response({"error": "email, password, and client_name are required"}, status=400)

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.check_password(password):
            return Response({"error": "401 Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        token = UserApiToken.create_for_request(user, client_name, request)
        token.set_active()
        return Response({"token": token.token, "expire_at": token.expire_at})


class UserMeView(generics.RetrieveAPIView):
    """Mirrors API::Users#me — GET /users/me."""

    serializer_class = UserMeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserEventsView(generics.ListAPIView):
    """Mirrors API::Users#events — GET /users/events."""

    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Event.objects.filter(
            pk__in=self.request.user.registered_participation().values_list("event_id", flat=True)
        ).order_by("-start_time")


class UserSessionsView(generics.ListAPIView):
    """Mirrors API::Users#sessions — GET /users/sessions."""

    serializer_class = EventSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.request.user.speaker_sessions()
