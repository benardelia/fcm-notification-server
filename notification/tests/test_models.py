"""
Unit tests for notification models.
Tests model methods, properties, and constraints.
"""
import pytest
from django.utils import timezone
from datetime import timedelta

from .factories import (
    ApiClientFactory, ProfileFactory, DeviceFactory,
    NotificationFactory, NotificationTemplateFactory, WebhookEndpointFactory,
)


@pytest.mark.django_db
class TestApiClientModel:

    def test_str_representation(self):
        client = ApiClientFactory()
        assert client.name in str(client)
        assert str(client.client_id) in str(client)

    def test_is_authenticated_always_true(self):
        client = ApiClientFactory()
        assert client.is_authenticated is True

    def test_token_valid_when_no_expiry(self):
        client = ApiClientFactory(expires_at=None)
        assert client.is_token_valid() is True

    def test_token_valid_when_not_expired(self):
        future = timezone.now() + timedelta(days=30)
        client = ApiClientFactory(expires_at=future)
        assert client.is_token_valid() is True

    def test_token_invalid_when_expired(self):
        past = timezone.now() - timedelta(days=1)
        client = ApiClientFactory(expires_at=past)
        assert client.is_token_valid() is False

    def test_has_scope_no_scopes_set(self):
        """Empty scopes = unrestricted (backward compatible)."""
        client = ApiClientFactory(scopes=[])
        assert client.has_scope('send') is True
        assert client.has_scope('admin') is True

    def test_has_scope_with_specific_scopes(self):
        client = ApiClientFactory(scopes=['send', 'read'])
        assert client.has_scope('send') is True
        assert client.has_scope('read') is True
        assert client.has_scope('manage') is False

    def test_has_scope_admin_grants_all(self):
        client = ApiClientFactory(scopes=['admin'])
        assert client.has_scope('send') is True
        assert client.has_scope('read') is True
        assert client.has_scope('manage') is True

    def test_ip_allowed_empty_list(self):
        """Empty allowed_ips = all IPs allowed."""
        client = ApiClientFactory(allowed_ips=[])
        assert client.is_ip_allowed('1.2.3.4') is True
        assert client.is_ip_allowed('192.168.0.1') is True

    def test_ip_allowed_with_whitelist(self):
        client = ApiClientFactory(allowed_ips=['10.0.0.1', '10.0.0.2'])
        assert client.is_ip_allowed('10.0.0.1') is True
        assert client.is_ip_allowed('10.0.0.2') is True
        assert client.is_ip_allowed('10.0.0.3') is False


@pytest.mark.django_db
class TestProfileModel:

    def test_str_with_phone_number(self):
        profile = ProfileFactory(phone_number='+255700123456', email=None)
        assert '+255700123456' in str(profile)

    def test_str_with_email_only(self):
        profile = ProfileFactory(phone_number=None, email='user@example.com')
        assert 'user@example.com' in str(profile)

    def test_str_fallback_to_pk(self):
        from notification.models import Profile
        p = Profile(phone_number=None, email=None, is_active=True)
        p.pk = 99
        assert 'Profile #99' in str(p)

    def test_profile_with_phone_only(self):
        profile = ProfileFactory(phone_number='+255700000001', email=None)
        assert profile.phone_number == '+255700000001'
        assert profile.email is None

    def test_profile_with_email_only(self):
        profile = ProfileFactory(phone_number=None, email='hello@example.com')
        assert profile.email == 'hello@example.com'
        assert profile.phone_number is None

    def test_profile_with_both_identifiers(self):
        profile = ProfileFactory(phone_number='+255700000002', email='both@example.com')
        assert profile.phone_number == '+255700000002'
        assert profile.email == 'both@example.com'

    def test_clean_raises_if_no_identifier(self):
        from notification.models import Profile
        from django.core.exceptions import ValidationError
        p = Profile(phone_number=None, email=None, is_active=True)
        with pytest.raises(ValidationError, match='at least a phone number or an email'):
            p.clean()

    def test_profile_active_by_default(self):
        profile = ProfileFactory()
        assert profile.is_active is True


@pytest.mark.django_db
class TestDeviceModel:

    def test_str_representation(self):
        device = DeviceFactory()
        assert device.profile.phone_number in str(device)
        assert device.device_type in str(device)

    def test_device_types(self):
        for device_type in ['iOS', 'Android', 'Web']:
            device = DeviceFactory(device_type=device_type)
            assert device.device_type == device_type

    def test_push_token_unique(self):
        DeviceFactory(push_token='token-abc-123')
        with pytest.raises(Exception):
            DeviceFactory(push_token='token-abc-123')


@pytest.mark.django_db
class TestNotificationModel:

    def test_str_with_title(self):
        n = NotificationFactory(title='Hello World')
        assert 'Hello World' in str(n)

    def test_str_silent_notification(self):
        n = NotificationFactory(title='', is_silent=True)
        assert 'Silent notification' in str(n)

    def test_default_priority_high(self):
        n = NotificationFactory()
        assert n.priority == 'high'

    def test_default_status_pending(self):
        n = NotificationFactory()
        assert n.status == 'pending'


@pytest.mark.django_db
class TestNotificationTemplateModel:

    def test_str_representation(self):
        tmpl = NotificationTemplateFactory(name='order-confirm')
        assert 'order-confirm' in str(tmpl)

    def test_active_by_default(self):
        tmpl = NotificationTemplateFactory()
        assert tmpl.is_active is True


@pytest.mark.django_db
class TestWebhookEndpointModel:

    def test_str_representation(self):
        webhook = WebhookEndpointFactory(url='https://example.com/hook/')
        assert 'https://example.com/hook/' in str(webhook)

    def test_events_stored_as_list(self):
        webhook = WebhookEndpointFactory(events=['notification.sent'])
        webhook.refresh_from_db()
        assert isinstance(webhook.events, list)
        assert 'notification.sent' in webhook.events
