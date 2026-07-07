from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


def user_has_mfa(user):
    from allauth.mfa.models import Authenticator

    return Authenticator.objects.filter(user=user).exists()


class Privileged2FAMiddleware:
    """Rev 3 (closes gap #4): when REQUIRE_2FA_FOR_PRIVILEGED is on,
    staff can't use /admin/ and chapter leads can't use /leads/ until
    they've enrolled a TOTP authenticator (allauth.mfa's activation
    flow at /accounts/2fa/totp/activate). Regular members are never
    affected."""

    PROTECTED = (("/admin/", "is_staff"), ("/leads/", "is_leader"))

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.REQUIRE_2FA_FOR_PRIVILEGED and request.user.is_authenticated:
            path = request.path
            # never trap the user out of the MFA setup/auth pages themselves
            if not path.startswith("/accounts/"):
                for prefix, check in self.PROTECTED:
                    if path.startswith(prefix) and self._is_privileged(request.user, check):
                        if not user_has_mfa(request.user):
                            messages.warning(
                                request,
                                "Two-factor authentication is required for this area — "
                                "set up an authenticator app to continue.",
                            )
                            return redirect(reverse("mfa_activate_totp"))
                        break
        return self.get_response(request)

    @staticmethod
    def _is_privileged(user, check):
        if check == "is_staff":
            return user.is_staff
        return user.is_leader()
