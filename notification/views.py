import logging

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view

from notification.middleware import ApiClientAuthentication
from .serializers import (
    ProfileSerializer, DeviceSerializer, NotificationSerializer,
    NotificationDeliveryLogSerializer, TopicSerializer, UserTopicSerializer,
    SendNotificationSerializer, BulkSendNotificationSerializer,
    TopicNotificationSerializer, FirebaseProjectSerializer,
    NotificationTemplateSerializer, NotificationAnalyticsSerializer,
    WebhookEndpointSerializer, ScheduledNotificationSerializer,
    TemplateSendSerializer, TemplateBulkSendSerializer,
)
from .models import (
    Profile, Device, Notification, NotificationDeliveryLog,
    Topic, UserTopic, FirebaseProject, NotificationTemplate,
    NotificationAnalytics, WebhookEndpoint, ScheduledNotification,
)
from .filters import (
    ProfileFilter, DeviceFilter, NotificationFilter,
    DeliveryLogFilter, TopicFilter, NotificationTemplateFilter,
    AnalyticsFilter, ScheduledNotificationFilter,
)
from .services import FCMService, dispatch_webhook, render_notification_template

logger = logging.getLogger(__name__)


# ============================================================
# Notification Sending Views
# ============================================================

@extend_schema(tags=['Notifications'])
class SendNotificationView(APIView):
    """
    Send a notification to a single profile's devices by phone number.

    Automatically sends to **all active devices** registered under the profile.
    - 1 device: uses direct FCM send
    - 2+ devices: uses FCM multicast (single API call)
    """

    @extend_schema(
        request=SendNotificationSerializer,
        responses={200: dict},
        summary="Send notification to a phone number",
    )
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
                {"success": False, "error": {"code": "not_found", "message": "No active device found for this profile."}},
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
                response_id = fcm.send_to_device(
                    token=tokens[0], title=title, body=body,
                    data=data, image_url=image_url, priority=priority,
                )
                results.append({"device_id": devices[0].pk, "status": "sent", "response": str(response_id)})
                NotificationDeliveryLog.objects.create(
                    notification=notification, device=devices[0],
                    delivered_at=timezone.now(), status="sent",
                )
            else:
                response = fcm.send_multicast(
                    tokens=tokens, title=title, body=body,
                    data=data, image_url=image_url, priority=priority,
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
                        notification=notification, device=device,
                        delivered_at=timezone.now() if individual_status == "sent" else None,
                        status=individual_status, error_message=error_message,
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
                {"success": False, "error": {"code": "send_failed", "message": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema(tags=['Notifications'])
class BulkSendNotificationView(APIView):
    """
    Send a notification to multiple phone numbers at once.

    Collects all active devices across the provided phone numbers
    and sends via FCM multicast (up to 500 tokens per call).
    """

    @extend_schema(
        request=BulkSendNotificationSerializer,
        responses={200: dict},
        summary="Bulk send notification to multiple phone numbers",
    )
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

        devices = Device.objects.filter(
            profile__phone_number__in=phone_numbers,
            is_active=True,
        ).select_related('profile')

        if not devices.exists():
            return Response(
                {"success": False, "error": {"code": "not_found", "message": "No active devices found for the provided phone numbers."}},
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
                tokens=tokens, title=title, body=body,
                data=data, image_url=image_url, priority=priority,
            )

            notification = Notification.objects.create(
                title=title, body=body, data_payload=data,
                status="sent", sent_at=timezone.now(),
            )

            logs = []
            for i, device in enumerate(devices):
                individual_status = "sent"
                error_message = None
                if hasattr(response, 'responses') and i < len(response.responses):
                    if not response.responses[i].success:
                        individual_status = "failed"
                        error_message = str(response.responses[i].exception)
                logs.append(NotificationDeliveryLog(
                    notification=notification, device=device,
                    delivered_at=timezone.now() if individual_status == "sent" else None,
                    status=individual_status, error_message=error_message,
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
                {"success": False, "error": {"code": "send_failed", "message": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(tags=['Notifications'])
class TopicNotificationView(APIView):
    """
    Send a notification to all devices subscribed to an FCM topic.
    """

    @extend_schema(
        request=TopicNotificationSerializer,
        responses={200: dict},
        summary="Send notification to a topic",
    )
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
                topic=topic_name, title=title, body=body,
                data=data, image_url=image_url,
            )

            notification = Notification.objects.create(
                title=title, body=body,
                data_payload={**data, '_topic': topic_name},
                status="sent", sent_at=timezone.now(),
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
                {"success": False, "error": {"code": "send_failed", "message": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema(tags=['Notifications'])
class TemplateSendView(APIView):
    """
    Send a notification using a pre-defined template with variable substitution.

    Resolves the template by name, renders title/body with provided variables,
    and sends to all active devices for the given phone number.
    """

    @extend_schema(
        request=TemplateSendSerializer,
        responses={200: dict},
        summary="Send notification using a template",
    )
    def post(self, request):
        serializer = TemplateSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        template_name = serializer.validated_data['template_name']
        variables = serializer.validated_data.get('variables', {})
        phone_number = serializer.validated_data['phone_number']
        extra_data = serializer.validated_data.get('data', {})
        priority = serializer.validated_data.get('priority', 'high')
        is_silent = serializer.validated_data.get('is_silent', False)
        click_action = serializer.validated_data.get('click_action', '')
        firebase_project_id = serializer.validated_data.get('firebase_project_id')

        template = get_object_or_404(NotificationTemplate, name=template_name, is_active=True)
        rendered = render_notification_template(template, variables)

        profile = get_object_or_404(Profile, phone_number=phone_number)
        devices = profile.devices.filter(is_active=True)
        if not devices.exists():
            return Response(
                {"success": False, "error": {"code": "not_found", "message": "No active device found for this profile."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Merge rendered data with extra data
        merged_data = {**rendered.get('data', {}), **extra_data}

        firebase_project = None
        if firebase_project_id:
            firebase_project = get_object_or_404(FirebaseProject, pk=firebase_project_id, is_active=True)

        try:
            fcm = FCMService(firebase_project=firebase_project)
            tokens = [d.push_token for d in devices]

            notification = Notification.objects.create(
                title=rendered['title'],
                body=rendered['body'],
                data_payload=merged_data,
                image_url=template.platform_overrides.get('image_url', ''),
                priority=priority,
                is_silent=is_silent,
                click_action=click_action,
                template=template,
                template_variables=variables,
                status="sent",
                sent_at=timezone.now(),
            )

            if len(tokens) == 1:
                fcm.send_to_device(
                    token=tokens[0], title=rendered['title'], body=rendered['body'],
                    data=merged_data, priority=priority, is_silent=is_silent,
                    click_action=click_action,
                )
                NotificationDeliveryLog.objects.create(
                    notification=notification, device=devices[0],
                    delivered_at=timezone.now(), status="sent",
                )
            else:
                response = fcm.send_multicast(
                    tokens=tokens, title=rendered['title'], body=rendered['body'],
                    data=merged_data, priority=priority, is_silent=is_silent,
                    click_action=click_action,
                )
                for i, device in enumerate(devices):
                    ind_status = "sent"
                    error_msg = None
                    if hasattr(response, 'responses') and i < len(response.responses):
                        if not response.responses[i].success:
                            ind_status = "failed"
                            error_msg = str(response.responses[i].exception)
                    NotificationDeliveryLog.objects.create(
                        notification=notification, device=device,
                        delivered_at=timezone.now() if ind_status == "sent" else None,
                        status=ind_status, error_message=error_msg,
                    )

            return Response({
                "success": True,
                "message": f"Template '{template_name}' sent to {len(tokens)} device(s)",
                "notification_id": notification.pk,
                "rendered_title": rendered['title'],
                "rendered_body": rendered['body'],
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error sending template notification: {e}")
            return Response(
                {"success": False, "error": {"code": "send_failed", "message": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ============================================================
# Scheduled Notification Views
# ============================================================

@extend_schema_view(
    list=extend_schema(summary="List scheduled notifications", tags=['Scheduled Notifications']),
    create=extend_schema(summary="Create a scheduled notification", tags=['Scheduled Notifications']),
)
class ScheduledNotificationListCreateView(generics.ListCreateAPIView):
    serializer_class = ScheduledNotificationSerializer
    filterset_class = ScheduledNotificationFilter
    search_fields = ['title', 'body']
    ordering_fields = ['id', 'scheduled_at', 'next_run_at', 'status', 'created_at']
    ordering = ['-created_at']
    queryset = ScheduledNotification.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ScheduledNotification.objects.none()
        return ScheduledNotification.objects.filter(created_by=self.request.user)


@extend_schema_view(
    retrieve=extend_schema(summary="Get scheduled notification details", tags=['Scheduled Notifications']),
    update=extend_schema(summary="Update a scheduled notification", tags=['Scheduled Notifications']),
    partial_update=extend_schema(summary="Partial update a scheduled notification", tags=['Scheduled Notifications']),
    destroy=extend_schema(summary="Delete a scheduled notification", tags=['Scheduled Notifications']),
)
class ScheduledNotificationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ScheduledNotificationSerializer
    queryset = ScheduledNotification.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return ScheduledNotification.objects.none()
        return ScheduledNotification.objects.filter(created_by=self.request.user)


# ============================================================
# CRUD Views — with filtering, search, ordering
# ============================================================

@extend_schema_view(
    list=extend_schema(summary="List profiles", tags=['Profiles']),
    create=extend_schema(summary="Create a profile", tags=['Profiles']),
)
class ProfileListCreateView(generics.ListCreateAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    filterset_class = ProfileFilter
    search_fields = ['phone_number']
    ordering_fields = ['id', 'phone_number']
    ordering = ['id']


@extend_schema_view(
    retrieve=extend_schema(summary="Get profile details", tags=['Profiles']),
    update=extend_schema(summary="Update a profile", tags=['Profiles']),
    partial_update=extend_schema(summary="Partial update a profile", tags=['Profiles']),
    destroy=extend_schema(summary="Delete a profile", tags=['Profiles']),
)
class ProfileRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer


@extend_schema_view(
    list=extend_schema(summary="List devices", tags=['Devices']),
    create=extend_schema(summary="Register a device", tags=['Devices']),
)
class DeviceListCreateView(generics.ListCreateAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    filterset_class = DeviceFilter
    search_fields = ['push_token', 'profile__phone_number']
    ordering_fields = ['id', 'last_seen', 'device_type']
    ordering = ['-last_seen']


@extend_schema_view(
    retrieve=extend_schema(summary="Get device details", tags=['Devices']),
    update=extend_schema(summary="Update a device", tags=['Devices']),
    partial_update=extend_schema(summary="Partial update a device", tags=['Devices']),
    destroy=extend_schema(summary="Delete a device", tags=['Devices']),
)
class DeviceRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer


@extend_schema_view(
    list=extend_schema(summary="List notifications", tags=['Notifications']),
    create=extend_schema(summary="Create a notification record", tags=['Notifications']),
)
class NotificationListCreateView(generics.ListCreateAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    filterset_class = NotificationFilter
    search_fields = ['title', 'body']
    ordering_fields = ['id', 'created_at', 'sent_at', 'status']
    ordering = ['-created_at']


@extend_schema_view(
    retrieve=extend_schema(summary="Get notification details", tags=['Notifications']),
    update=extend_schema(summary="Update a notification", tags=['Notifications']),
    partial_update=extend_schema(summary="Partial update a notification", tags=['Notifications']),
    destroy=extend_schema(summary="Delete a notification", tags=['Notifications']),
)
class NotificationRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer


@extend_schema_view(
    list=extend_schema(summary="List delivery logs", tags=['Notifications']),
    create=extend_schema(summary="Create a delivery log", tags=['Notifications']),
)
class NotificationDeliveryLogListCreateView(generics.ListCreateAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer
    filterset_class = DeliveryLogFilter
    ordering_fields = ['id', 'delivered_at', 'read_at', 'status']
    ordering = ['-delivered_at']


@extend_schema_view(
    retrieve=extend_schema(summary="Get delivery log details", tags=['Notifications']),
    update=extend_schema(summary="Update a delivery log", tags=['Notifications']),
    partial_update=extend_schema(summary="Partial update a delivery log", tags=['Notifications']),
    destroy=extend_schema(summary="Delete a delivery log", tags=['Notifications']),
)
class NotificationDeliveryLogRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationDeliveryLog.objects.all()
    serializer_class = NotificationDeliveryLogSerializer


@extend_schema_view(
    list=extend_schema(summary="List topics", tags=['Topics']),
    create=extend_schema(summary="Create a topic", tags=['Topics']),
)
class TopicListCreateView(generics.ListCreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer
    filterset_class = TopicFilter
    search_fields = ['name', 'description']
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']


@extend_schema_view(
    retrieve=extend_schema(summary="Get topic details", tags=['Topics']),
    update=extend_schema(summary="Update a topic", tags=['Topics']),
    partial_update=extend_schema(summary="Partial update a topic", tags=['Topics']),
    destroy=extend_schema(summary="Delete a topic", tags=['Topics']),
)
class TopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicSerializer


@extend_schema_view(
    list=extend_schema(summary="List user-topic subscriptions", tags=['Topics']),
    create=extend_schema(summary="Subscribe user to topic", tags=['Topics']),
)
class UserTopicListCreateView(generics.ListCreateAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer


@extend_schema_view(
    retrieve=extend_schema(summary="Get user-topic details", tags=['Topics']),
    update=extend_schema(summary="Update user-topic", tags=['Topics']),
    partial_update=extend_schema(summary="Partial update user-topic", tags=['Topics']),
    destroy=extend_schema(summary="Unsubscribe user from topic", tags=['Topics']),
)
class UserTopicRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = UserTopic.objects.all()
    serializer_class = UserTopicSerializer
    authentication_classes = [ApiClientAuthentication]
    permission_classes = [IsAuthenticated]


# ============================================================
# Configuration API — Firebase Projects, Templates, Webhooks
# ============================================================

@extend_schema_view(
    list=extend_schema(summary="List your Firebase projects", tags=['Firebase Projects']),
    create=extend_schema(summary="Register a Firebase project", tags=['Firebase Projects']),
)
class FirebaseProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = FirebaseProjectSerializer
    queryset = FirebaseProject.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FirebaseProject.objects.none()
        return FirebaseProject.objects.filter(api_client=self.request.user)


@extend_schema_view(
    retrieve=extend_schema(summary="Get Firebase project details", tags=['Firebase Projects']),
    update=extend_schema(summary="Update a Firebase project", tags=['Firebase Projects']),
    partial_update=extend_schema(summary="Partial update a Firebase project", tags=['Firebase Projects']),
    destroy=extend_schema(summary="Delete a Firebase project", tags=['Firebase Projects']),
)
class FirebaseProjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FirebaseProjectSerializer
    queryset = FirebaseProject.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return FirebaseProject.objects.none()
        return FirebaseProject.objects.filter(api_client=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List notification templates", tags=['Templates']),
    create=extend_schema(summary="Create a notification template", tags=['Templates']),
)
class NotificationTemplateListCreateView(generics.ListCreateAPIView):
    queryset = NotificationTemplate.objects.filter(is_active=True)
    serializer_class = NotificationTemplateSerializer
    filterset_class = NotificationTemplateFilter
    search_fields = ['name', 'title_template', 'body_template']
    ordering_fields = ['id', 'name', 'created_at']
    ordering = ['name']


@extend_schema_view(
    retrieve=extend_schema(summary="Get template details", tags=['Templates']),
    update=extend_schema(summary="Update a template", tags=['Templates']),
    partial_update=extend_schema(summary="Partial update a template", tags=['Templates']),
    destroy=extend_schema(summary="Delete a template", tags=['Templates']),
)
class NotificationTemplateRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer


@extend_schema_view(
    list=extend_schema(summary="List your webhooks", tags=['Webhooks']),
    create=extend_schema(summary="Register a webhook endpoint", tags=['Webhooks']),
)
class WebhookEndpointListCreateView(generics.ListCreateAPIView):
    serializer_class = WebhookEndpointSerializer
    queryset = WebhookEndpoint.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WebhookEndpoint.objects.none()
        return WebhookEndpoint.objects.filter(api_client=self.request.user)


@extend_schema_view(
    retrieve=extend_schema(summary="Get webhook details", tags=['Webhooks']),
    update=extend_schema(summary="Update a webhook", tags=['Webhooks']),
    partial_update=extend_schema(summary="Partial update a webhook", tags=['Webhooks']),
    destroy=extend_schema(summary="Delete a webhook", tags=['Webhooks']),
)
class WebhookEndpointRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = WebhookEndpointSerializer
    queryset = WebhookEndpoint.objects.none()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return WebhookEndpoint.objects.none()
        return WebhookEndpoint.objects.filter(api_client=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="List notification analytics", tags=['Analytics']),
)
class NotificationAnalyticsListView(generics.ListAPIView):
    queryset = NotificationAnalytics.objects.all().order_by('-date')
    serializer_class = NotificationAnalyticsSerializer
    filterset_class = AnalyticsFilter
    ordering_fields = ['date', 'total_sent', 'total_delivered', 'total_failed']
    ordering = ['-date']


# ============================================================
# Health Check
# ============================================================

@extend_schema(tags=['Health'])
class HealthCheckView(APIView):
    """
    Service health check endpoint.

    Returns the status of database, Redis cache, and Firebase SDK.
    No authentication required.
    """
    permission_classes = []
    authentication_classes = []

    @extend_schema(summary="Check service health", responses={200: dict})
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
            firebase_admin.get_app()
            health['firebase'] = 'healthy'
        except Exception:
            health['firebase'] = 'not initialized (will init on first send)'

        all_healthy = all(
            v == 'healthy' for v in health.values()
            if v != 'not initialized (will init on first send)'
        )
        http_status = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response({
            'status': 'healthy' if all_healthy else 'degraded',
            'services': health,
        }, status=http_status)
