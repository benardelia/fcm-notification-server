import datetime
import json
import tempfile
import os
import logging

import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache of initialized Firebase apps keyed by project name
_firebase_apps = {}


class FCMService:
    """
    Multi-tenant Firebase Cloud Messaging service.

    Supports:
    - Default credentials from FIREBASE_CREDENTIALS_PATH env var
    - Per-client Firebase projects via FirebaseProject model
    - Send to single device, multiple devices, topics, and conditions
    """

    def __init__(self, firebase_project=None):
        """
        Initialize with an optional FirebaseProject model instance.
        If None, uses the default credentials from settings.
        """
        self.app = self._get_or_create_app(firebase_project)

    def _get_or_create_app(self, firebase_project=None):
        """Get an existing Firebase app or create a new one."""
        if firebase_project is None:
            # Use default credentials from environment
            app_name = '[DEFAULT]'
            if app_name in _firebase_apps:
                return _firebase_apps[app_name]

            cred_path = settings.FIREBASE_CREDENTIALS_PATH
            if not cred_path:
                raise ValueError(
                    "FIREBASE_CREDENTIALS_PATH not set in environment. "
                    "Either set it in .env or provide a FirebaseProject instance."
                )

            cred = credentials.Certificate(cred_path)
            if not firebase_admin._apps:
                app = firebase_admin.initialize_app(cred)
            else:
                app = firebase_admin.get_app()

            _firebase_apps[app_name] = app
            return app

        # Multi-tenant: use FirebaseProject credentials
        app_name = f"project_{firebase_project.pk}"
        if app_name in _firebase_apps:
            return _firebase_apps[app_name]

        # Write credentials JSON to a temp file for Firebase SDK
        cred_data = firebase_project.credentials_json
        if isinstance(cred_data, str):
            cred_data = json.loads(cred_data)

        cred = credentials.Certificate(cred_data)

        try:
            app = firebase_admin.get_app(name=app_name)
        except ValueError:
            app = firebase_admin.initialize_app(cred, name=app_name)

        _firebase_apps[app_name] = app
        return app

    def send_to_device(self, token, title, body, data=None, image_url=None, priority='high'):
        """Send a notification to a single device token."""
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        )

        android_config = messaging.AndroidConfig(
            ttl=datetime.timedelta(seconds=3600),
            priority=priority,
            notification=messaging.AndroidNotification(
                icon="ic_launcher",
                color='#f45342',
            ),
        )

        apns_config = messaging.APNSConfig(
            headers={'apns-priority': '10' if priority == 'high' else '5'},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(badge=42),
            ),
        )

        webpush_config = messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                title=title,
                body=body,
                icon=image_url or '',
            ),
        )

        # Ensure all data values are strings (FCM requirement)
        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.Message(
            notification=notification,
            data=str_data,
            android=android_config,
            apns=apns_config,
            webpush=webpush_config,
            token=token,
        )

        response = messaging.send(message, app=self.app)
        logger.info(f"Sent notification to token {token[:20]}...: {response}")
        return response

    def send_multicast(self, tokens, title, body, data=None, image_url=None, priority='high'):
        """Send a notification to multiple device tokens (up to 500)."""
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        )

        android_config = messaging.AndroidConfig(
            ttl=datetime.timedelta(seconds=3600),
            priority=priority,
            notification=messaging.AndroidNotification(
                icon="ic_launcher",
                color='#f45342',
            ),
        )

        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.MulticastMessage(
            notification=notification,
            data=str_data,
            android=android_config,
            tokens=tokens,
        )

        response = messaging.send_each_for_multicast(message, app=self.app)
        logger.info(
            f"Multicast sent: {response.success_count} success, "
            f"{response.failure_count} failures"
        )
        return response

    def send_to_topic(self, topic, title, body, data=None, image_url=None):
        """Send a notification to all devices subscribed to a topic."""
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        )

        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.Message(
            notification=notification,
            data=str_data,
            topic=topic,
        )

        response = messaging.send(message, app=self.app)
        logger.info(f"Sent notification to topic '{topic}': {response}")
        return response

    def send_to_condition(self, condition, title, body, data=None, image_url=None):
        """Send a notification to devices matching a topic condition."""
        notification = messaging.Notification(
            title=title,
            body=body,
            image=image_url,
        )

        str_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.Message(
            notification=notification,
            data=str_data,
            condition=condition,
        )

        response = messaging.send(message, app=self.app)
        logger.info(f"Sent notification to condition '{condition}': {response}")
        return response

    def subscribe_to_topic(self, tokens, topic):
        """Subscribe device tokens to a topic."""
        response = messaging.subscribe_to_topic(tokens, topic, app=self.app)
        logger.info(f"Subscribed {response.success_count} tokens to '{topic}'")
        return response

    def unsubscribe_from_topic(self, tokens, topic):
        """Unsubscribe device tokens from a topic."""
        response = messaging.unsubscribe_from_topic(tokens, topic, app=self.app)
        logger.info(f"Unsubscribed {response.success_count} tokens from '{topic}'")
        return response
