from rest_framework import serializers

from apps.accounts.models import User
from apps.chapters.models import Chapter
from apps.events.models import Event, EventRegistration, EventSession


class ChapterSerializer(serializers.ModelSerializer):
    """Mirrors API::ChapterEntity."""

    class Meta:
        model = Chapter
        fields = ["id", "name", "created_at", "updated_at"]


class EventSerializer(serializers.ModelSerializer):
    """Mirrors API::EventEntity."""

    event_type = serializers.CharField(source="event_type.name")
    chapter = ChapterSerializer()

    class Meta:
        model = Event
        fields = ["id", "event_type", "chapter", "name", "description", "start_time", "end_time"]


class EventSessionSerializer(serializers.ModelSerializer):
    """Mirrors API::EventSessionEntity."""

    tags = serializers.SerializerMethodField()

    class Meta:
        model = EventSession
        fields = [
            "id",
            "name",
            "description",
            "session_type",
            "tags",
            "presentation_url",
            "video_url",
            "start_time",
            "end_time",
        ]

    def get_tags(self, obj):
        return ", ".join(t.name for t in obj.tags.all())


class UserSerializer(serializers.ModelSerializer):
    """Mirrors API::UserEntity (referenced by EventRegistrationEntity)."""

    class Meta:
        model = User
        fields = ["id", "name", "email", "handle", "avatar"]


class EventRegistrationSerializer(serializers.ModelSerializer):
    """Mirrors API::EventRegistrationEntity."""

    user = UserSerializer()

    class Meta:
        model = EventRegistration
        fields = ["id", "event_id", "user"]


class UserMeSerializer(serializers.ModelSerializer):
    """Mirrors the field list in API::Users#me."""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "homepage",
            "about_me",
            "twitter_handle",
            "facebook_profile",
            "github_profile",
            "linkedin_profile",
            "handle",
            "avatar",
            "updated_at",
            "created_at",
        ]
