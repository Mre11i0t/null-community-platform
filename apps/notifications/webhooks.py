"""Rev 3 outbound webhooks.

emit(chapter, kind, payload) fans out to every active endpoint the
chapter registered. Each delivery is HMAC-SHA256 signed with the
endpoint's secret (X-Null-Signature header) so receivers can verify
authenticity. Delivery runs through Celery with retries; every attempt
outcome lands in WebhookDelivery for the leads to inspect.
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

KINDS = ("event.published", "registration.created", "registration.checked_in")


class WebhookURLError(ValueError):
    """Endpoint URL rejected by the SSRF guard."""


def _resolved_addresses(hostname, port):
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as exc:
        raise WebhookURLError("Endpoint host does not resolve") from exc
    return {info[4][0] for info in infos}


def validate_webhook_url(url):
    """SSRF guard for chapter-registered endpoints: https only, and the host
    must resolve exclusively to public addresses — never loopback, private
    ranges, link-local (cloud metadata), or other reserved space. Callers
    re-check on every delivery because DNS can change after registration."""
    try:
        parsed = urlparse(url)
        hostname, port = parsed.hostname, parsed.port
    except ValueError as exc:
        raise WebhookURLError("Endpoint URL is invalid") from exc
    if parsed.scheme != "https" or not hostname:
        raise WebhookURLError("Endpoint must be an https:// URL with a host")
    for raw in _resolved_addresses(hostname, port or 443):
        if not ipaddress.ip_address(raw).is_global:
            raise WebhookURLError("Endpoint host resolves to a private or reserved address")
    return url


def emit(chapter, kind, payload):
    from .models import WebhookEndpoint

    for endpoint in WebhookEndpoint.objects.filter(chapter=chapter, active=True):
        deliver_webhook.delay(endpoint.pk, kind, payload)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def deliver_webhook(self, endpoint_id, kind, payload):
    import requests

    from .models import WebhookDelivery, WebhookEndpoint

    try:
        endpoint = WebhookEndpoint.objects.get(pk=endpoint_id, active=True)
    except WebhookEndpoint.DoesNotExist:
        return

    body = json.dumps({"kind": kind, "data": payload, "sent_at": timezone.now().isoformat()})
    signature = hmac.new(endpoint.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    delivery = WebhookDelivery(endpoint=endpoint, kind=kind, payload=payload)
    try:
        validate_webhook_url(endpoint.url)
    except WebhookURLError as exc:
        delivery.error = str(exc)[:255]
        delivery.save()
        return
    try:
        response = requests.post(
            endpoint.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Null-Signature": f"sha256={signature}",
                "X-Null-Event": kind,
            },
            timeout=10,
            # never follow redirects: they could re-point the signed POST at
            # internal services the URL guard already vetoed
            allow_redirects=False,
        )
        delivery.response_status = response.status_code
        if response.status_code < 300:
            delivery.delivered_at = timezone.now()
        delivery.save()
        if response.status_code >= 300:
            raise self.retry()
    except requests.RequestException as exc:
        delivery.error = str(exc)[:255]
        delivery.save()
        raise self.retry(exc=exc)
