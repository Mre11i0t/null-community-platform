from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.accounts.models import UserApiToken


class ApiTokenAuthentication(authentication.BaseAuthentication):
    """Validates the `X-Access-Token` header against UserApiToken,
    mirroring the original /api-v2 token auth (24h expiry, invalidated
    on password change — see UserApiToken model).
    """

    def authenticate(self, request):
        token = request.headers.get("X-Access-Token")
        if not token:
            return None

        try:
            api_token = UserApiToken.objects.select_related("user").get(token=token, active=True)
        except UserApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid or inactive API token")

        if api_token.expire_at and api_token.expire_at < timezone.now():
            raise exceptions.AuthenticationFailed("API token expired")

        return (api_token.user, api_token)
