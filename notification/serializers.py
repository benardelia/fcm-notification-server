from rest_framework import serializers
from .models import (
    Profile, Device, Notification, NotificationDeliveryLog,
    Topic, UserTopic, FirebaseProject,
    NotificationTemplate, NotificationAnalytics, WebhookEndpoint,
    ScheduledNotification,
)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = '__all__'
        

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'
        

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        

class NotificationDeliveryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDeliveryLog
        fields = '__all__'
        

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = '__all__'
        

class UserTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTopic
        fields = '__all__'


# ------------------------------
# Send Notification Serializers
# ------------------------------
class SendNotificationSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    data = serializers.JSONField(required=False, default=dict)
    image_url = serializers.URLField(required=False, allow_blank=True, default='')
    priority = serializers.ChoiceField(choices=['high', 'normal'], default='high')
    firebase_project_id = serializers.IntegerField(required=False, help_text="Optional: use a specific Firebase project for multi-tenant sending")


class BulkSendNotificationSerializer(serializers.Serializer):
    phone_numbers = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=500,
    )
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    data = serializers.JSONField(required=False, default=dict)
    image_url = serializers.URLField(required=False, allow_blank=True, default='')
    priority = serializers.ChoiceField(choices=['high', 'normal'], default='high')
    firebase_project_id = serializers.IntegerField(required=False)


class TopicNotificationSerializer(serializers.Serializer):
    topic = serializers.CharField(max_length=100)
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    data = serializers.JSONField(required=False, default=dict)
    image_url = serializers.URLField(required=False, allow_blank=True, default='')
    firebase_project_id = serializers.IntegerField(required=False)


# ------------------------------
# Configuration Serializers
# ------------------------------
class FirebaseProjectSerializer(serializers.ModelSerializer):
    credentials_json = serializers.JSONField(write_only=True)

    class Meta:
        model = FirebaseProject
        fields = ['id', 'api_client', 'project_name', 'credentials_json', 'is_default', 'is_active', 'created_at']
        read_only_fields = ['id', 'api_client', 'created_at']

    def create(self, validated_data):
        # Automatically set api_client from the authenticated client
        validated_data['api_client'] = self.context['request'].user
        return super().create(validated_data)


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class NotificationAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationAnalytics
        fields = '__all__'


class ScheduledNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledNotification
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'next_run_at', 'last_sent_at', 'occurrence_count']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        # Set next_run_at to scheduled_at initially
        if 'next_run_at' not in validated_data or validated_data.get('next_run_at') is None:
            validated_data['next_run_at'] = validated_data.get('scheduled_at')
        return super().create(validated_data)


class TemplateSendSerializer(serializers.Serializer):
    """Send a notification using a pre-defined template with variable substitution."""
    template_name = serializers.CharField(max_length=100, help_text="Name of the NotificationTemplate to use")
    variables = serializers.JSONField(required=False, default=dict, help_text="Variables to substitute into the template: {\"name\": \"John\"}")
    phone_number = serializers.CharField(help_text="Target phone number")
    data = serializers.JSONField(required=False, default=dict)
    priority = serializers.ChoiceField(choices=['high', 'normal'], default='high')
    is_silent = serializers.BooleanField(default=False)
    click_action = serializers.URLField(required=False, allow_blank=True, default='')
    firebase_project_id = serializers.IntegerField(required=False)


class TemplateBulkSendSerializer(serializers.Serializer):
    """Bulk send using a template."""
    template_name = serializers.CharField(max_length=100)
    variables = serializers.JSONField(required=False, default=dict)
    phone_numbers = serializers.ListField(child=serializers.CharField(), min_length=1, max_length=500)
    data = serializers.JSONField(required=False, default=dict)
    priority = serializers.ChoiceField(choices=['high', 'normal'], default='high')
    firebase_project_id = serializers.IntegerField(required=False)


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = ['id', 'url', 'events', 'secret_key', 'is_active', 'failure_count', 'last_triggered_at', 'created_at']
        read_only_fields = ['id', 'failure_count', 'last_triggered_at', 'created_at']
        extra_kwargs = {
            'secret_key': {'write_only': True},
        }

    def create(self, validated_data):
        validated_data['api_client'] = self.context['request'].user
        return super().create(validated_data)
