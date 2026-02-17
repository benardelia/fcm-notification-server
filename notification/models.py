import uuid
from django.db import models
from django.contrib.auth.models import User


# ------------------------------
# User (extend Django's built-in)
# ------------------------------
# If you need custom fields beyond the built-in User,
# you can extend it via OneToOne relation.
class Profile(models.Model):
    # user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.phone_number


# ------------------------------
# Devices
# ------------------------------
class Device(models.Model):
    DEVICE_TYPES = (
        ("iOS", "iOS"),
        ("Android", "Android"),
        ("Web", "Web"),
    )

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="devices")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    push_token = models.CharField(max_length=512, unique=True)  # APNs / FCM token
    last_seen = models.DateTimeField(auto_now=True)
    app_version = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.profile.phone_number} - {self.device_type}"


# ------------------------------
# Notifications
# ------------------------------
class Notification(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    )

    title = models.CharField(max_length=255)
    body = models.TextField()
    data_payload = models.JSONField(blank=True, null=True)  # Extra metadata
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return self.title


# ------------------------------
# Delivery Log
# ------------------------------
class NotificationDeliveryLog(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("read", "Read"),
    )

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="deliveries")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="deliveries")
    delivered_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.notification.title} → {self.device}"


# ------------------------------
# Topics (for groups/broadcast)
# ------------------------------
class Topic(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserTopic(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="topics")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="subscribers")

    class Meta:
        unique_together = ("user", "topic")

    def __str__(self):
        return f"{self.user.username} → {self.topic.name}"



class ApiClient(models.Model):
    name = models.CharField(max_length=100, unique=True)   # e.g. "Mobile App", "Web Dashboard"
    client_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    auth_token = models.CharField(max_length=255, unique=True)  # pre-generated token
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ID: ({self.client_id}) token: {self.auth_token}"
    
    @property
    def is_authenticated(self):
        """DRF expects this attribute on the user object."""
        return True
    


# ------------------------------
# Firebase Projects (multi-tenant)
# ------------------------------
class FirebaseProject(models.Model):
    api_client = models.ForeignKey(ApiClient, on_delete=models.CASCADE, related_name="firebase_projects")
    project_name = models.CharField(max_length=100)
    credentials_json = models.JSONField()  # Store the full service account JSON
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.project_name} ({self.api_client.name})"

    class Meta:
        unique_together = ('api_client', 'project_name')


# ------------------------------
# Notification Templates
# ------------------------------
class NotificationTemplate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    title_template = models.CharField(max_length=255)
    body_template = models.TextField()
    default_data = models.JSONField(default=dict, blank=True)
    platform_overrides = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(ApiClient, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


# ------------------------------
# Analytics
# ------------------------------
class NotificationAnalytics(models.Model):
    date = models.DateField()
    api_client = models.ForeignKey(ApiClient, on_delete=models.CASCADE, null=True)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    platform = models.CharField(max_length=10, blank=True)
    total_sent = models.IntegerField(default=0)
    total_delivered = models.IntegerField(default=0)
    total_read = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    avg_delivery_time_ms = models.IntegerField(null=True)

    class Meta:
        unique_together = ('date', 'api_client', 'topic', 'platform')

    def __str__(self):
        return f"Analytics {self.date} - {self.platform or 'all'}"


# ------------------------------
# Webhooks
# ------------------------------
class WebhookEndpoint(models.Model):
    EVENT_CHOICES = [
        ('notification.sent', 'Notification Sent'),
        ('notification.delivered', 'Notification Delivered'),
        ('notification.read', 'Notification Read'),
        ('notification.failed', 'Notification Failed'),
        ('device.registered', 'Device Registered'),
        ('device.deactivated', 'Device Deactivated'),
    ]

    api_client = models.ForeignKey(ApiClient, on_delete=models.CASCADE)
    url = models.URLField()
    events = models.JSONField(default=list)  # List of event types to subscribe to
    secret_key = models.CharField(max_length=255)  # For HMAC signature verification
    is_active = models.BooleanField(default=True)
    failure_count = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.url} ({self.api_client.name})"