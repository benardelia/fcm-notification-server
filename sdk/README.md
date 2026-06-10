# FCM Server Client SDK

A lightweight Python client for the [FCM Notification Server](../README.md) API.

## Installation

```bash
# From PyPI (once published)
pip install fcm-server-client

# Or directly from the repo (development)
pip install -e path/to/fcm_server/sdk/
```

## Quick Start

```python
from fcm_client import FCMClient

client = FCMClient(
    base_url="https://your-fcm-server.com",
    client_id="your-client-uuid",
    client_token="your-auth-token",
)

# Send a single notification
response = client.send(
    phone_number="+255712345678",
    title="Order Confirmed",
    body="Your order #1234 is ready.",
    data={"order_id": "1234", "screen": "order_details"},
)
print(response)  # {'success': True, 'notification_id': 42, ...}
```

## Features

| Method | Description |
|---|---|
| `client.send(...)` | Send notification to a single phone number |
| `client.bulk_send(...)` | Send to multiple phone numbers at once |
| `client.send_to_topic(...)` | Broadcast to an FCM topic |
| `client.send_template(...)` | Send using a pre-defined template |
| `client.register_device(...)` | Register a device token |
| `client.create_profile(...)` | Create a user profile |
| `client.list_notifications(...)` | List sent notifications |
| `client.health()` | Check server health |

## Authentication

Every request requires two headers:
- `Client-ID` — your UUID from the admin panel
- `Client-Token` — your secret token

```python
client = FCMClient(
    base_url="https://your-server.com",
    client_id="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    client_token="your-secret-token",
)
```

## Idempotency

Prevent duplicate sends on retry by passing an `idempotency_key`:

```python
client.send(
    phone_number="+255712345678",
    title="Payment Received",
    body="We got your payment.",
    idempotency_key="payment-txn-id-9876",  # safe to retry with same key
)
```

## Sending with Templates

```python
# Create template once via the API, then use it by name
client.send_template(
    template_name="order-confirmed",
    phone_number="+255712345678",
    variables={"name": "John", "order_id": "1234", "status": "ready"},
)
```

## Bulk Sending

```python
client.bulk_send(
    phone_numbers=["+255700001111", "+255700002222", "+255700003333"],
    title="Flash Sale!",
    body="50% off for the next 2 hours.",
    priority="high",
)
```

## Error Handling

```python
from fcm_client import FCMClient, FCMClientError

try:
    client.send(phone_number="+255700000000", title="T", body="B")
except FCMClientError as e:
    print(e.status_code)  # HTTP status
    print(e.error_code)   # API error code string
    print(e.message)      # Human-readable message
```

## Full API Reference

See the server's interactive docs at `https://your-server.com/api/docs/`.
