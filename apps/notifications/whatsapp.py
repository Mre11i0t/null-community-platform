"""Rev 3 WhatsApp Business Cloud API adapter.

Env-gated like every other integration in the rewrite: with
WHATSAPP_API_TOKEN + WHATSAPP_PHONE_NUMBER_ID configured it POSTs to
Meta's Graph API; without them it logs the message and does nothing —
so dev, tests, and a deployment that never buys WhatsApp all behave
sensibly. Recipients must have opted in via the preference center
(whatsapp_enabled + whatsapp_number).
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_number_id}/messages"


def whatsapp_configured():
    return bool(settings.WHATSAPP_API_TOKEN and settings.WHATSAPP_PHONE_NUMBER_ID)


def _mask(number):
    """Recipient numbers are personal data — logs get the last 4 digits only."""
    return f"…{number[-4:]}" if number else number


def send_whatsapp(to_number, message):
    """Send a text message; returns True if actually dispatched."""
    if not to_number:
        return False
    if not whatsapp_configured():
        logger.info("WhatsApp (dry-run, not configured) to %s: %s", _mask(to_number), message[:120])
        return False

    import requests

    response = requests.post(
        GRAPH_URL.format(phone_number_id=settings.WHATSAPP_PHONE_NUMBER_ID),
        headers={"Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}"},
        json={
            "messaging_product": "whatsapp",
            "to": to_number.lstrip("+"),
            "type": "text",
            "text": {"body": message[:4096]},
        },
        timeout=10,
    )
    if response.status_code >= 400:
        # log only stable identifiers from the error payload — Meta error
        # bodies can echo the recipient's phone number
        try:
            error = response.json().get("error") or {}
        except (ValueError, AttributeError):
            error = {}
        logger.warning(
            "WhatsApp send failed (HTTP %s): error code=%s type=%s",
            response.status_code,
            error.get("code"),
            error.get("type"),
        )
        return False
    return True
