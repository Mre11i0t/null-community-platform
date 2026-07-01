import re

from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.accounts.models import UserApiToken


class ApiTokenAuthentication(authentication.BaseAuthentication):
    """Validates the `Authorization: Bearer <token>` header against
    UserApiToken, mirroring API::Helper#authenticate_api_user! (24h
    expiry, invalidated on password change — see UserApiToken model).
    """

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        token = re.sub(r"(?i)^bearer\s+", "", header).strip()
        if not token:
            return None

        try:
            api_token = UserApiToken.objects.select_related("user").get(token=token, active=True)
        except UserApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Authentication required!")

        if api_token.expire_at and api_token.expire_at < timezone.now():
            raise exceptions.AuthenticationFailed("Authentication required!")

        return (api_token.user, api_token)

    def authenticate_header(self, request):
        # Presence of this method makes DRF return 401 (not 403) for
        # missing/invalid credentials, matching the original's
        # `error!('Authentication required!', 401)`.
        return "Bearer"
