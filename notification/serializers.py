from rest_framework import serializers
from .models import *


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
