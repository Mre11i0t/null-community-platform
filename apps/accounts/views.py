from django.shortcuts import get_object_or_404, render

from .models import User


def public_profile(request, pk):
    """Mirrors HomeController#public_profile."""
    user = get_object_or_404(User, pk=pk)
    speaker_sessions = user.speaker_sessions()
    # Rev 3: topics spoken on (tag cloud) + co-speaker credits
    topics = sorted({tag.name for session in speaker_sessions for tag in session.tags.all()})
    return render(
        request,
        "accounts/public_profile.html",
        {
            "profile_user": user,
            "speaker_sessions": speaker_sessions,
            "co_speaker_sessions": user.co_speaker_sessions.filter(deleted_at__isnull=True),
            "topics": topics,
            "registered_participation": user.registered_participation(),
            "achievements": user.achievements.all(),
        },
    )
