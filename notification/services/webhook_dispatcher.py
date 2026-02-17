import hashlib
import hmac
import json
import logging
from threading import Thread

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_FAILURE_COUNT = 10


def _generate_signature(payload_bytes, secret_key):
    """Generate HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret_key.encode('utf-8'),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def _deliver_webhook(webhook, payload):
    """Deliver a single webhook request."""
    payload_bytes = json.dumps(payload, default=str).encode('utf-8')
    signature = _generate_signature(payload_bytes, webhook.secret_key)

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': signature,
        'X-Webhook-Event': payload.get('event', ''),
    }

    try:
        response = requests.post(
            webhook.url,
            data=payload_bytes,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

        # Success — reset failure count
        webhook.failure_count = 0
        webhook.last_triggered_at = timezone.now()
        webhook.save(update_fields=['failure_count', 'last_triggered_at'])

        logger.info(f"Webhook delivered: {webhook.url} ({response.status_code})")

    except requests.RequestException as e:
        webhook.failure_count += 1
        webhook.last_triggered_at = timezone.now()

        # Auto-deactivate after too many consecutive failures
        if webhook.failure_count >= MAX_FAILURE_COUNT:
            webhook.is_active = False
            logger.warning(
                f"Webhook deactivated after {MAX_FAILURE_COUNT} failures: {webhook.url}"
            )

        webhook.save(update_fields=['failure_count', 'last_triggered_at', 'is_active'])
        logger.error(f"Webhook delivery failed: {webhook.url} — {e}")


def dispatch_webhook(event_type, payload, api_client):
    """
    Dispatch a webhook event to all registered endpoints for the given API client.

    Args:
        event_type: One of the WebhookEndpoint.EVENT_CHOICES values
                    (e.g. 'notification.sent', 'notification.delivered')
        payload: Dict with event data to send
        api_client: The ApiClient instance that triggered the event
    """
    from notification.models import WebhookEndpoint

    webhooks = WebhookEndpoint.objects.filter(
        api_client=api_client,
        is_active=True,
    )

    # Filter to webhooks that subscribe to this event type
    matching = [w for w in webhooks if event_type in (w.events or [])]

    if not matching:
        return

    full_payload = {
        'event': event_type,
        'timestamp': timezone.now().isoformat(),
        'data': payload,
    }

    # Dispatch each webhook in a background thread to avoid blocking the response
    for webhook in matching:
        thread = Thread(target=_deliver_webhook, args=(webhook, full_payload))
        thread.daemon = True
        thread.start()
