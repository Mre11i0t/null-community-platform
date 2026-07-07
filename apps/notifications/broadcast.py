"""Rev 3 social broadcast — replaces the dead Twitter-via-IFTTT path.

One message fans out to every *configured* channel; unconfigured
channels silently skip (env-gated like all integrations here). The free
webhook channels (Discord/Slack/Telegram) are the default path; X is
optional because its API is pay-per-use ($0.20/post with a link).
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def broadcast(message):
    """Send `message` to every configured channel; returns channel names
    that accepted it."""
    delivered = []
    for name, sender in (
        ("discord", _send_discord),
        ("slack", _send_slack),
        ("telegram", _send_telegram),
        ("x", _send_x),
    ):
        try:
            if sender(message):
                delivered.append(name)
        except Exception:  # one broken channel must not stop the rest
            logger.exception("Broadcast to %s failed", name)
    return delivered


def _send_discord(message):
    if not settings.DISCORD_WEBHOOK_URL:
        return False
    import requests

    requests.post(settings.DISCORD_WEBHOOK_URL, json={"content": message[:2000]}, timeout=10)
    return True


def _send_slack(message):
    if not settings.SLACK_WEBHOOK_URL:
        return False
    import requests

    requests.post(settings.SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    return True


def _send_telegram(message):
    if not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID):
        return False
    import requests

    requests.post(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": message},
        timeout=10,
    )
    return True


def _send_x(message):
    """X API v2 create-post (OAuth 1.0a user context). Pay-per-use for
    new developer accounts — keep an eye on volume."""
    if not (settings.X_CONSUMER_KEY and settings.X_ACCESS_TOKEN):
        return False
    import requests
    from requests_oauthlib import OAuth1

    auth = OAuth1(
        settings.X_CONSUMER_KEY,
        settings.X_CONSUMER_SECRET,
        settings.X_ACCESS_TOKEN,
        settings.X_ACCESS_TOKEN_SECRET,
    )
    response = requests.post(
        "https://api.twitter.com/2/tweets",
        json={"text": message[:280]},
        auth=auth,
        timeout=10,
    )
    if response.status_code >= 400:
        logger.warning("X post failed (%s): %s", response.status_code, response.text[:200])
        return False
    return True
