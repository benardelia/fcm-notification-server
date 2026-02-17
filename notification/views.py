import logging

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from notification.middleware import ApiClientAuthentication
from .serializers import (
    ProfileSerializer, DeviceSerializer, NotificationSerializer,
    NotificationDeliveryLogSerializer, TopicSerializer, UserTopicSerializer,
    SendNotificationSerializer, BulkSendNotificationSerializer,
    TopicNotificationSerializer, FirebaseProjectSerializer,
    NotificationTemplateSerializer, NotificationAnalyticsSerializer,
    WebhookEndpointSerializer,
)
from .models import (
    Profile, Device, Notification, NotificationDeliveryLog,
    Topic, UserTopic, FirebaseProject, NotificationTemplate,
    NotificationAnalytics, WebhookEndpoint,
)
from .services import FCMService, dispatch_webhook

logger = logging.getLogger(__name__)


# ============================================================
# Notification Sending Views
# ============================================================

class SendNotificationView(APIView):
    """
    Send a notification to a single device by phone number.

    POST /notification/notify/
    {
        "phone_number": "+255712345678",
        "title": "Hello",
        "body": "World",
        "data": {"key": "value"},
        "image_url": "https://example.com/image.png",
        "priority": "high",
        "firebase_project_id": 1  // optional, for multi-tenant
    }
    """

    def post(self, request):
        serializer = SendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        title = serializer.validated_data['title']
        body = serializer.validated_data['body']
        data = serializer.validated_data.get('data', {})
        image_url = serializer.validated_data.get('image_url', '')
        priority = serializer.validated_data.get('priority', 'high')
        firebase_project_id = serializer.validated_data.get('firebase_project_id')

        profile = get_object_or_404(Profile, phone_number=phone_number)
        devices = profile.devices.filter(is_active=True)
        if not devices.exists():
            return Response(
                {"error": "No active device found for this profile."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Resolve Firebase project (multi-tenant or default)
        firebase_project = None
        if firebase_project_id:
            firebase_project = get_object_or_404(
                FirebaseProject, pk=firebase_project_id, is_active=True
            )

        try:
            fcm = FCMService(firebase_project=firebase_project)

            notification = Notification.objects.create(
                title=title,
                body=body,
                data_payload=data,
                status="sent",
                sent_at=timezone.now(),
            )

            # Send to ALL active devices for this profile
            tokens = [d.push_token for d in devices]
            results = []

            if len(tokens) == 1:
                # Single device — direct send
                response_id = fcm.send_to_device(
                    token=tokens[0],
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url,
                    priority=priority,
                )
                results.append({"device_id": devices[0].pk, "status": "sent", "response": str(response_id)})
                NotificationDeliveryLog.objects.create(
                    notification=notification,
                    device=devices[0],
                    delivered_at=timezone.now(),
                    status="sent",
                )
            else:
                # Multiple devices — multicast
                response = fcm.send_multicast(
                    tokens=tokens,
                    title=title,
                    body=body,
                    data=data,
                    image_url=image_url,
                    priority=priority,
                )
                for i, device in enumerate(devices):
                    individual_status = "sent"
                    error_message = None
                    if hasattr(response, 'responses') and i < len(response.responses):
                        if not response.responses[i].success:
                            individual_status = "failed"
                            error_message = str(response.responses[i].exception)

                    results.append({
                        "device_id": device.pk,
                        "device_type": device.device_type,
                        "status": individual_status,
                        "error": error_message,
                    })
                    NotificationDeliveryLog.objects.create(
                        notification=notification,
                        device=device,
                        delivered_at=timezone.now() if individual_status == "sent" else None,
                        status=individual_status,
                        error_message=error_message,
                    )

            # Dispatch webhook event
            api_client = getattr(request, 'user', None)
            if api_client and hasattr(api_client, 'pk'):
                dispatch_webhook('notification.sent', {
                    'notification_id': notification.pk,
                    'phone_number': phone_number,
                    'title': title,
                    'devices_count': len(tokens),
                }, api_client)

            return Response({
                "success": True,
                "message": f"Notification sent to {len(tokens)} device(s)",
                "notification_id": notification.pk,
                "devices": results,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BulkSendNotificationView(APIView):
    """
    Send a notification to multiple phone numbers at once.

    POST /notification/notify/bulk/
    {
        "phone_numbers": ["+255712345678", "+255712345679"],
        "title": "Announcement",
        "body": "Important update",
        "data": {"key": "value"}
    }
    """

    def post(self, request):
        serializer = BulkSendNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_numbers = serializer.validated_data['phone_numbers']
        title = serializer.validated_data['title']
        body = serializer.validated_data['body']
        data = serializer.validated_data.get('data', {})
        image_url = serializer.validated_data.get('image_url', '')
        priority = serializer.validated_data.get('priority', 'high')
        firebase_project_id = serializer.validated_data.get('firebase_project_id')

        # Collect active device tokens
        devices = Device.objects.filter(
            profile__phone_number__in=phone_numbers,
            is_active=True,
        ).select_related('profile')

        if not devices.exists():
            return Response(
                {"error": "No active devices found for the provided phone numbers."},
                status=status.HTTP_404_NOT_FOUND,
            )

        tokens = [d.push_token for d in devices]

        firebase_project = None
        if firebase_project_id:
            firebase_project = get_object_or_404(
                FirebaseProject, pk=firebase_project_id, is_active=True
            )

        try:
            fcm = FCMService(firebase_project=firebase_project)
            response = fcm.send_multicast(
                tokens=tokens,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
                priority=priority,
            )

            notification = Notification.objects.create(
                title=title,
                body=body,
                data_payload=data,
                status="sent",
                sent_at=timezone.now(),
            )

            # Create delivery logs for each device
            logs = []
            for i, device in enumerate(devices):
                individual_status = "sent"
                error_message = None
                if hasattr(response, 'responses') and i < len(response.responses):
                    if not response.responses[i].success:
                        individual_status = "failed"
                        error_message = str(response.responses[i].exception)

                logs.append(NotificationDeliveryLog(
                    notification=notification,
                    device=device,
                    delivered_at=timezone.now() if individual_status == "sent" else None,
                    status=individual_status,
                    error_message=error_message,
                ))
            NotificationDeliveryLog.objects.bulk_create(logs)

            return Response({
                "success": True,
                "message": "Bulk notification sent",
                "notification_id": notification.pk,
                "total_devices": len(tokens),
                "success_count": response.success_count,
                "failure_count": response.failure_count,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending bulk notification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TopicNotificationView(APIView):
    """
    Send a notification to all subscribers of a topic.

    POST /notification/notify/topic/
    {
        "topic": "news",
        "title": "Breaking News",
        "body": "Something happened"
    }
    """

    def post(self, request):
        serializer = TopicNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_name = serializer.validated_data['topic']
        title = serializer.validated_data['title']
        body = serializer.validated_data['body']
        data = serializer.validated_data.get('data', {})
        image_url = serializer.validated_data.get('image_url', '')
        firebase_project_id = serializer.validated_data.get('firebase_project_id')

        firebase_project = None
        if firebase_project_id:
            firebase_project = get_object_or_404(
                FirebaseProject, pk=firebase_project_id, is_active=True
            )

        try:
            fcm = FCMService(firebase_project=firebase_project)
            response_id = fcm.send_to_topic(
                topic=topic_name,
                title=title,
                body=body,
                data=data,
                image_url=image_url,
            )

            notification = Notification.objects.create(
                title=title,
                body=body,
                data_payload={**data, '_topic': topic_name},
                status="sent",
                sent_at=timezone.now(),
            )

            return Response({
                "success": True,
                "message": f"Notification sent to topic '{topic_name}'",
                "notification_id": notification.pk,
                "fcm_response": str(response_id),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending topic notification: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# CRUD Views — Existing Models
# ============================================================

class ProfileListCreateView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer

class ProfileRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


class DeviceListCreateView(generics.ListCreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class DeviceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer

class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

class NotificationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

class NotificationDeliveryLogListCreateView(generics.ListCreateAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer

class NotificationDeliveryLogRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer

class TopicListCreateView(generics.ListCreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class TopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer

class UserTopicListCreateView(generics.ListCreateAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer

class UserTopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer
    authentication_classes = [ApiClientAuthentication]
    permission_classes = [IsAuthenticated]


# ============================================================
# Configuration API — Firebase Projects, Templates, Webhooks
# ============================================================

class FirebaseProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = FirebaseProjectSerializer

    def get_queryset(self):
        # Only show Firebase projects belonging to the authenticated client
        return FirebaseProject.objects.filter(api_client=self.request.user)


class FirebaseProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FirebaseProjectSerializer

    def get_queryset(self):
        return FirebaseProject.objects.filter(api_client=self.request.user)


class NotificationTemplateListCreateView(generics.ListCreateAPIView):
    queryset = NotificationTemplate.objects.filter(is_active=True)
    serializer_class = NotificationTemplateSerializer


class NotificationTemplateRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer


class WebhookEndpointListCreateView(generics.ListCreateAPIView):
    serializer_class = WebhookEndpointSerializer

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(api_client=self.request.user)


class WebhookEndpointRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WebhookEndpointSerializer

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(api_client=self.request.user)


class NotificationAnalyticsListView(generics.ListAPIView):
    queryset = NotificationAnalytics.objects.all().order_by('-date')
    serializer_class = NotificationAnalyticsSerializer


# ============================================================
# Health Check
# ============================================================

class HealthCheckView(APIView):
    """
    GET /health/

    Returns the health status of all services:
    - database: PostgreSQL connection
    - redis: Redis connection
    - firebase: Firebase SDK initialized
    """
    permission_classes = []  # Public endpoint, no auth required
    authentication_classes = []

    def get(self, request):
        health = {}

        # Check database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health['database'] = 'healthy'
        except Exception as e:
            health['database'] = f'unhealthy: {e}'

        # Check Redis
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                health['redis'] = 'healthy'
            else:
                health['redis'] = 'unhealthy: cache read failed'
        except Exception as e:
            health['redis'] = f'unhealthy: {e}'

        # Check Firebase
        try:
            import firebase_admin
            app = firebase_admin.get_app()
            health['firebase'] = 'healthy'
        except Exception:
            health['firebase'] = 'not initialized (will init on first send)'

        all_healthy = all(v == 'healthy' for v in health.values() if v != 'not initialized (will init on first send)')
        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            'status': 'healthy' if all_healthy else 'degraded',
            'services': health,
        }, status=http_status)
