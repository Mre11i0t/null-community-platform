"""Rev 3 outbound webhooks.

emit(chapter, kind, payload) fans out to every active endpoint the
chapter registered. Each delivery is HMAC-SHA256 signed with the
endpoint's secret (X-Null-Signature header) so receivers can verify
authenticity. Delivery runs through Celery with retries; every attempt
outcome lands in WebhookDelivery for the leads to inspect.
"""

import hashlib
import hmac
import json
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

KINDS = ("event.published", "registration.created", "registration.checked_in")


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
        response = requests.post(
            endpoint.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Null-Signature": f"sha256={signature}",
                "X-Null-Event": kind,
            },
            timeout=10,
        )
        delivery.response_status = response.status_code
        if response.status_code < 400:
            delivery.delivered_at = timezone.now()
        delivery.save()
        if response.status_code >= 400:
            raise self.retry()
    except requests.RequestException as exc:
        delivery.error = str(exc)[:255]
        delivery.save()
        raise self.retry(exc=exc)
