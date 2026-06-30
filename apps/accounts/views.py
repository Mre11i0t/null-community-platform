from django.shortcuts import get_object_or_404, render

from .models import User


def public_profile(request, pk):
    """Mirrors HomeController#public_profile."""
    user = get_object_or_404(User, pk=pk)
    return render(
        request,
        "accounts/public_profile.html",
        {
            "profile_user": user,
            "speaker_sessions": user.speaker_sessions(),
            "registered_participation": user.registered_participation(),
            "achievements": user.achievements.all(),
        },
    )
