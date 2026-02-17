"""
FCM Notification Server - Python Client SDK

Usage:
    from sdk import FCMClient

    client = FCMClient(
        base_url="http://localhost:8000",
        client_id="your-client-uuid",
        client_token="your-auth-token",
    )

    # Send a single notification
    result = client.send_notification(
        phone_number="+255712345678",
        title="Hello",
        body="World",
        data={"screen": "home"},
    )

    # Send to multiple recipients
    result = client.send_bulk(
        phone_numbers=["+255712345678", "+255712345679"],
        title="Announcement",
        body="Important update",
    )

    # Send to a topic
    result = client.send_to_topic(
        topic="news",
        title="Breaking",
        body="Something happened",
    )
"""

import requests


class FCMClientError(Exception):
    """Raised when the FCM server returns an error."""
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"[{status_code}] {detail}")


class FCMClient:
    """Python client for the FCM Notification Server API."""

    def __init__(self, base_url, client_id, client_token, timeout=30):
        """
        Args:
            base_url: The server URL, e.g. "http://localhost:8000"
            client_id: Your ApiClient UUID
            client_token: Your ApiClient auth token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Client-ID': str(client_id),
            'Client-Token': str(client_token),
            'Content-Type': 'application/json',
        })

    def _url(self, path):
        return f"{self.base_url}/notification/{path.lstrip('/')}"

    def _request(self, method, path, json=None, params=None):
        response = self.session.request(
            method=method,
            url=self._url(path),
            json=json,
            params=params,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise FCMClientError(response.status_code, detail)
        return response.json()

    # ----------------------------------
    # Notification Sending
    # ----------------------------------

    def send_notification(self, phone_number, title, body, data=None,
                          image_url=None, priority='high', firebase_project_id=None):
        """Send a notification to a single device by phone number."""
        payload = {
            'phone_number': phone_number,
            'title': title,
            'body': body,
            'data': data or {},
            'priority': priority,
        }
        if image_url:
            payload['image_url'] = image_url
        if firebase_project_id:
            payload['firebase_project_id'] = firebase_project_id
        return self._request('POST', 'notify/', json=payload)

    def send_bulk(self, phone_numbers, title, body, data=None,
                  image_url=None, priority='high', firebase_project_id=None):
        """Send a notification to multiple phone numbers."""
        payload = {
            'phone_numbers': phone_numbers,
            'title': title,
            'body': body,
            'data': data or {},
            'priority': priority,
        }
        if image_url:
            payload['image_url'] = image_url
        if firebase_project_id:
            payload['firebase_project_id'] = firebase_project_id
        return self._request('POST', 'notify/bulk/', json=payload)

    def send_to_topic(self, topic, title, body, data=None,
                      image_url=None, firebase_project_id=None):
        """Send a notification to all subscribers of a topic."""
        payload = {
            'topic': topic,
            'title': title,
            'body': body,
            'data': data or {},
        }
        if image_url:
            payload['image_url'] = image_url
        if firebase_project_id:
            payload['firebase_project_id'] = firebase_project_id
        return self._request('POST', 'notify/topic/', json=payload)

    # ----------------------------------
    # Device Management
    # ----------------------------------

    def list_devices(self):
        """List all registered devices."""
        return self._request('GET', 'device/')

    def register_device(self, profile_id, device_type, push_token, app_version=None):
        """Register a new device."""
        payload = {
            'profile': profile_id,
            'device_type': device_type,
            'push_token': push_token,
        }
        if app_version:
            payload['app_version'] = app_version
        return self._request('POST', 'device/', json=payload)

    def delete_device(self, device_id):
        """Remove a device."""
        return self._request('DELETE', f'device/{device_id}/')

    # ----------------------------------
    # Profile Management
    # ----------------------------------

    def list_profiles(self):
        """List all profiles."""
        return self._request('GET', 'profile/')

    def create_profile(self, phone_number):
        """Create a new profile."""
        return self._request('POST', 'profile/', json={'phone_number': phone_number})

    def get_profile(self, profile_id):
        """Get profile details."""
        return self._request('GET', f'profile/{profile_id}/')

    # ----------------------------------
    # Topic Management
    # ----------------------------------

    def list_topics(self):
        """List all topics."""
        return self._request('GET', 'topic/')

    def create_topic(self, name, description=''):
        """Create a new topic."""
        return self._request('POST', 'topic/', json={
            'name': name,
            'description': description,
        })

    # ----------------------------------
    # Webhook Management
    # ----------------------------------

    def list_webhooks(self):
        """List all webhooks for the authenticated client."""
        return self._request('GET', 'webhooks/')

    def create_webhook(self, url, events, secret_key):
        """
        Register a webhook endpoint.

        Args:
            url: The callback URL
            events: List of event types, e.g. ['notification.sent', 'notification.read']
            secret_key: Secret for HMAC signature verification
        """
        return self._request('POST', 'webhooks/', json={
            'url': url,
            'events': events,
            'secret_key': secret_key,
        })

    def delete_webhook(self, webhook_id):
        """Remove a webhook endpoint."""
        return self._request('DELETE', f'webhooks/{webhook_id}/')

    # ----------------------------------
    # Firebase Project Management
    # ----------------------------------

    def list_firebase_projects(self):
        """List Firebase projects for the authenticated client."""
        return self._request('GET', 'firebase-projects/')

    def create_firebase_project(self, project_name, credentials_json, is_default=False):
        """
        Register a Firebase project for multi-tenant notification sending.

        Args:
            project_name: A name for this Firebase project
            credentials_json: The full service account JSON dict
            is_default: Whether this is the default project for this client
        """
        return self._request('POST', 'firebase-projects/', json={
            'project_name': project_name,
            'credentials_json': credentials_json,
            'is_default': is_default,
        })

    def delete_firebase_project(self, project_id):
        """Remove a Firebase project."""
        return self._request('DELETE', f'firebase-projects/{project_id}/')

    # ----------------------------------
    # Templates
    # ----------------------------------

    def list_templates(self):
        """List notification templates."""
        return self._request('GET', 'templates/')

    def create_template(self, name, title_template, body_template,
                        default_data=None, platform_overrides=None):
        """Create a notification template."""
        return self._request('POST', 'templates/', json={
            'name': name,
            'title_template': title_template,
            'body_template': body_template,
            'default_data': default_data or {},
            'platform_overrides': platform_overrides or {},
        })

    # ----------------------------------
    # Analytics
    # ----------------------------------

    def get_analytics(self):
        """Get notification analytics."""
        return self._request('GET', 'analytics/')

    # ----------------------------------
    # Delivery Logs
    # ----------------------------------

    def list_delivery_logs(self):
        """List delivery logs."""
        return self._request('GET', 'delivery-log/')

    def get_delivery_log(self, log_id):
        """Get a specific delivery log."""
        return self._request('GET', f'delivery-log/{log_id}/')
