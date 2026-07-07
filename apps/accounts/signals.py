"""Rails-parity signals for the accounts app."""

from allauth.account.signals import password_changed, password_reset
from django.dispatch import receiver


@receiver(password_changed)
@receiver(password_reset)
def invalidate_api_tokens(sender, request, user, **kwargs):
    """Ports the original User#invalidate_api_tokens! callback: changing
    or resetting the password kills every active API token, so a stolen
    token dies with the compromised password."""
    user.api_tokens.update(active=False)
