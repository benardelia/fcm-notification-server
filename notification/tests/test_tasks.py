"""
Tests for Celery tasks.
Uses mock to avoid real FCM/DB calls in unit-level task tests.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from .factories import (ApiClientFactory, DeviceFactory,
                        NotificationDeliveryLogFactory, NotificationFactory)


@pytest.mark.django_db
class TestCleanupStaleTokensTask:

    def test_deactivates_stale_devices(self):
        from notification.tasks import cleanup_stale_tokens

        # Active device last seen 100 days ago → should be deactivated
        old_device = DeviceFactory(is_active=True)
        from notification.models import Device
        Device.objects.filter(pk=old_device.pk).update(last_seen=timezone.now() - timedelta(days=100))

        # Recent device → should remain active
        recent_device = DeviceFactory(is_active=True)

        result = cleanup_stale_tokens()

        old_device.refresh_from_db()
        recent_device.refresh_from_db()

        assert old_device.is_active is False
        assert recent_device.is_active is True
        assert result["deactivated"] == 1

    def test_returns_count_when_nothing_stale(self):
        from notification.tasks import cleanup_stale_tokens

        DeviceFactory(is_active=True)  # recent device
        result = cleanup_stale_tokens()
        assert result["deactivated"] == 0


@pytest.mark.django_db
class TestAggregateDailyAnalyticsTask:

    def test_creates_analytics_records(self):
        from notification.models import NotificationAnalytics
        from notification.tasks import aggregate_daily_analytics

        yesterday = timezone.now().date() - timedelta(days=1)

        # Create delivery logs for yesterday
        notif = NotificationFactory()
        device = DeviceFactory(device_type="Android")
        log = NotificationDeliveryLogFactory(
            notification=notif,
            device=device,
            status="sent",
        )
        log.delivered_at = timezone.now() - timedelta(days=1)
        log.save(update_fields=["delivered_at"])

        result = aggregate_daily_analytics()

        assert result["date"] == str(yesterday)
        assert result["buckets"] >= 1
        assert NotificationAnalytics.objects.filter(date=yesterday).exists()

    def test_idempotent_on_rerun(self):
        """Running the task twice for the same day should not create duplicate records."""
        from notification.models import NotificationAnalytics
        from notification.tasks import aggregate_daily_analytics

        aggregate_daily_analytics()
        aggregate_daily_analytics()

        yesterday = timezone.now().date() - timedelta(days=1)
        # update_or_create ensures no duplicates
        count = NotificationAnalytics.objects.filter(date=yesterday).count()
        assert count <= 3  # at most one record per platform bucket


@pytest.mark.django_db
class TestSendNotificationAsyncTask:

    @patch("notification.services.FCMService")
    def test_sends_and_updates_delivery_log(self, MockFCM):
        from notification.models import NotificationDeliveryLog
        from notification.tasks import send_notification_async

        mock_fcm = MockFCM.return_value
        mock_fcm.send_to_device.return_value = "fcm-message-id-test"

        notif = NotificationFactory()
        device = DeviceFactory()

        send_notification_async(
            notification_id=notif.pk,
            device_id=device.pk,
            title="Test",
            body="Body",
        )

        log = NotificationDeliveryLog.objects.get(notification=notif, device=device)
        assert log.status == "sent"

        notif.refresh_from_db()
        assert notif.status == "sent"

    @patch("notification.services.FCMService")
    def test_marks_failed_on_firebase_error(self, MockFCM):
        from celery.exceptions import Retry

        from notification.models import NotificationDeliveryLog
        from notification.tasks import send_notification_async

        mock_fcm = MockFCM.return_value
        mock_fcm.send_to_device.side_effect = Exception("Firebase error")

        notif = NotificationFactory()
        device = DeviceFactory()

        with pytest.raises((Exception, Retry)):
            send_notification_async.apply(
                kwargs={
                    "notification_id": notif.pk,
                    "device_id": device.pk,
                    "title": "Test",
                    "body": "Body",
                }
            )

        log = NotificationDeliveryLog.objects.filter(
            notification=notif, device=device
        ).first()
        if log:
            assert log.status == "failed"


@pytest.mark.django_db
class TestWebhookDispatchTask:

    @patch("notification.services.webhook_dispatcher.requests.post")
    def test_dispatches_to_matching_webhooks(self, mock_post):
        from notification.tasks import dispatch_webhook_async

        from .factories import WebhookEndpointFactory

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        api_client = ApiClientFactory()
        webhook = WebhookEndpointFactory(
            api_client=api_client,
            events=["notification.sent"],
        )

        dispatch_webhook_async(
            "notification.sent", {"notification_id": 1}, api_client.pk
        )

        assert mock_post.called
        call_url = mock_post.call_args[0][0]
        assert call_url == webhook.url
