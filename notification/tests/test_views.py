"""
Integration tests for API views.
Uses the Django test client with mocked Firebase calls.
"""

from unittest.mock import patch

import pytest

from .factories import (ApiClientFactory, DeviceFactory,
                        NotificationTemplateFactory, ProfileFactory)


def auth_headers(client):
    """Return auth headers for an ApiClient."""
    return {
        "HTTP_CLIENT_ID": str(client.client_id),
        "HTTP_CLIENT_TOKEN": client.auth_token,
    }


@pytest.mark.django_db
class TestHealthCheckView:

    def test_health_check_no_auth_required(self, client):
        response = client.get("/health/")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "services" in data

    def test_health_check_has_database_key(self, client):
        response = client.get("/health/")
        data = response.json()
        assert "database" in data["services"]


@pytest.mark.django_db
class TestSendNotificationView:

    @patch("notification.views.FCMService")
    def test_send_notification_success(self, MockFCM, client):
        mock_fcm = MockFCM.return_value
        mock_fcm.send_to_device.return_value = "fcm-message-id-123"

        api_client = ApiClientFactory()
        profile = ProfileFactory(phone_number="+255700111222")
        DeviceFactory(profile=profile, push_token="valid-token-001")

        response = client.post(
            "/api/v1/notify/",
            data={
                "phone_number": "+255700111222",
                "title": "Test Title",
                "body": "Test Body",
            },
            content_type="application/json",
            **auth_headers(api_client),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["notification_id"] is not None

    def test_send_notification_no_auth(self, client):
        response = client.post(
            "/api/v1/notify/",
            data={"phone_number": "+255700000000", "title": "T", "body": "B"},
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_send_notification_profile_not_found(self, client):
        api_client = ApiClientFactory()
        response = client.post(
            "/api/v1/notify/",
            data={"phone_number": "+255799999999", "title": "T", "body": "B"},
            content_type="application/json",
            **auth_headers(api_client),
        )
        assert response.status_code == 404

    def test_send_notification_no_active_devices(self, client):
        api_client = ApiClientFactory()
        profile = ProfileFactory(phone_number="+255700333444")
        DeviceFactory(profile=profile, is_active=False)

        response = client.post(
            "/api/v1/notify/",
            data={"phone_number": "+255700333444", "title": "T", "body": "B"},
            content_type="application/json",
            **auth_headers(api_client),
        )
        assert response.status_code == 404

    @patch("notification.views.FCMService")
    def test_idempotency_key_prevents_duplicate(self, MockFCM, client):
        mock_fcm = MockFCM.return_value
        mock_fcm.send_to_device.return_value = "fcm-id-456"

        api_client = ApiClientFactory()
        profile = ProfileFactory(phone_number="+255700555666")
        DeviceFactory(profile=profile, push_token="valid-token-002")

        payload = {"phone_number": "+255700555666", "title": "T", "body": "B"}
        headers = {**auth_headers(api_client), "HTTP_IDEMPOTENCY_KEY": "unique-key-001"}

        r1 = client.post(
            "/api/v1/notify/", data=payload, content_type="application/json", **headers
        )
        r2 = client.post(
            "/api/v1/notify/", data=payload, content_type="application/json", **headers
        )

        assert r1.status_code == 200
        assert r2.status_code == 200
        # FCM should only be called ONCE — second request uses cached response
        assert mock_fcm.send_to_device.call_count == 1


@pytest.mark.django_db
class TestDeviceEndpoints:

    def test_register_device(self, client):
        api_client = ApiClientFactory()
        profile = ProfileFactory(phone_number="+255700777888")

        response = client.post(
            "/api/v1/device/",
            data={
                "profile": profile.pk,
                "device_type": "Android",
                "push_token": "new-fcm-token-xyz-001",
            },
            content_type="application/json",
            **auth_headers(api_client),
        )
        assert response.status_code == 201

    def test_list_devices(self, client):
        api_client = ApiClientFactory()
        profile = ProfileFactory()
        DeviceFactory.create_batch(3, profile=profile)

        response = client.get("/api/v1/device/", **auth_headers(api_client))
        assert response.status_code == 200
        data = response.json()
        assert "results" in data


@pytest.mark.django_db
class TestProfileEndpoints:

    def test_create_profile(self, client):
        api_client = ApiClientFactory()
        response = client.post(
            "/api/v1/profile/",
            data={"phone_number": "+255700100200", "is_active": True},
            content_type="application/json",
            **auth_headers(api_client),
        )
        assert response.status_code == 201

    def test_list_profiles(self, client):
        api_client = ApiClientFactory()
        ProfileFactory.create_batch(5)
        response = client.get("/api/v1/profile/", **auth_headers(api_client))
        assert response.status_code == 200


@pytest.mark.django_db
class TestTemplateEndpoints:

    def test_create_template(self, client):
        api_client = ApiClientFactory()
        response = client.post(
            "/api/v1/templates/",
            data={
                "name": "welcome-msg",
                "title_template": "Welcome {{name}}!",
                "body_template": "Hi {{name}}, thanks for joining.",
                "created_by": api_client.pk,
            },
            content_type="application/json",
            **auth_headers(api_client),
        )
        assert response.status_code == 201

    def test_list_templates(self, client):
        api_client = ApiClientFactory()
        NotificationTemplateFactory.create_batch(3, created_by=api_client)
        response = client.get("/api/v1/templates/", **auth_headers(api_client))
        assert response.status_code == 200


@pytest.mark.django_db
class TestAuthMiddleware:

    def test_expired_token_returns_403(self, client):
        from datetime import timedelta

        from django.utils import timezone

        past = timezone.now() - timedelta(days=1)
        api_client = ApiClientFactory(expires_at=past)

        response = client.get("/api/v1/profile/", **auth_headers(api_client))
        assert response.status_code == 403

    def test_ip_not_whitelisted_returns_403(self, client):
        api_client = ApiClientFactory(allowed_ips=["10.0.0.1"])
        # Default test client REMOTE_ADDR is '127.0.0.1'
        response = client.get("/api/v1/profile/", **auth_headers(api_client))
        assert response.status_code == 403
