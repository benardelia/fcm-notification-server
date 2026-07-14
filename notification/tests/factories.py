"""
factory_boy factories for generating test data.
Used across all test modules to avoid repetitive setup code.
"""

import uuid

import factory
import factory.django
from django.utils import timezone


class ApiClientFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.ApiClient"

    name = factory.Sequence(lambda n: f"Test Client {n}")
    client_id = factory.LazyFunction(uuid.uuid4)
    auth_token = factory.Sequence(lambda n: f"test-token-{n}-{uuid.uuid4().hex}")
    description = "Factory-generated test client"
    is_active = True
    expires_at = None
    scopes = []
    allowed_ips = []


class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.Profile"

    phone_number = factory.Sequence(lambda n: f"+255700{n:06d}")
    email = None  # optional — set explicitly when needed
    is_active = True


class DeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.Device"

    profile = factory.SubFactory(ProfileFactory)
    device_type = "Android"
    push_token = factory.Sequence(lambda n: f"fcm-token-{n}-{uuid.uuid4().hex}")
    app_version = "1.0.0"
    is_active = True


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.Notification"

    title = factory.Sequence(lambda n: f"Test Notification {n}")
    body = "This is a test notification body."
    data_payload = {}
    status = "pending"
    priority = "high"
    is_silent = False


class NotificationDeliveryLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.NotificationDeliveryLog"

    notification = factory.SubFactory(NotificationFactory)
    device = factory.SubFactory(DeviceFactory)
    status = "sent"
    delivered_at = factory.LazyFunction(timezone.now)


class TopicFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.Topic"

    name = factory.Sequence(lambda n: f"test-topic-{n}")
    description = "A factory-generated test topic"


class NotificationTemplateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.NotificationTemplate"

    name = factory.Sequence(lambda n: f"test-template-{n}")
    title_template = "Hello {{name}}!"
    body_template = "Your order #{{order_id}} is {{status}}."
    default_data = {}
    is_active = True
    created_by = factory.SubFactory(ApiClientFactory)


class WebhookEndpointFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "notification.WebhookEndpoint"

    api_client = factory.SubFactory(ApiClientFactory)
    url = factory.Sequence(lambda n: f"https://example.com/webhook/{n}/")
    events = ["notification.sent", "notification.failed"]
    secret_key = factory.LazyFunction(lambda: uuid.uuid4().hex)
    is_active = True
    failure_count = 0
