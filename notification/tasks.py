import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_async(self, notification_id, device_id, firebase_project_id=None,
                            title='', body='', data=None, image_url='', priority='high'):
    """
    Send a push notification to a single device asynchronously.
    Retries up to 3 times with 60-second delay on failure.
    """
    from notification.models import Notification, Device, NotificationDeliveryLog, FirebaseProject
    from notification.services import FCMService

    try:
        notification = Notification.objects.get(pk=notification_id)
        device = Device.objects.get(pk=device_id)

        firebase_project = None
        if firebase_project_id:
            firebase_project = FirebaseProject.objects.get(pk=firebase_project_id, is_active=True)

        fcm = FCMService(firebase_project=firebase_project)
        response_id = fcm.send_to_device(
            token=device.push_token,
            title=title,
            body=body,
            data=data or {},
            image_url=image_url,
            priority=priority,
        )

        NotificationDeliveryLog.objects.update_or_create(
            notification=notification,
            device=device,
            defaults={
                'delivered_at': timezone.now(),
                'status': 'sent',
            },
        )

        logger.info(f"Async notification sent: {notification_id} -> device {device_id}")
        return {'status': 'sent', 'response': str(response_id)}

    except Exception as exc:
        logger.error(f"Async notification failed: {notification_id} -> device {device_id}: {exc}")

        # Update delivery log with failure
        try:
            from notification.models import Notification, Device, NotificationDeliveryLog
            NotificationDeliveryLog.objects.update_or_create(
                notification_id=notification_id,
                device_id=device_id,
                defaults={
                    'status': 'failed',
                    'error_message': str(exc),
                },
            )
        except Exception:
            pass

        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_bulk_notification_async(self, notification_id, device_ids, firebase_project_id=None,
                                 title='', body='', data=None, image_url='', priority='high'):
    """
    Send a push notification to multiple devices asynchronously via multicast.
    """
    from notification.models import Notification, Device, NotificationDeliveryLog, FirebaseProject
    from notification.services import FCMService

    try:
        notification = Notification.objects.get(pk=notification_id)
        devices = list(Device.objects.filter(pk__in=device_ids, is_active=True))
        tokens = [d.push_token for d in devices]

        if not tokens:
            logger.warning(f"No active devices for bulk notification {notification_id}")
            return {'status': 'no_devices'}

        firebase_project = None
        if firebase_project_id:
            firebase_project = FirebaseProject.objects.get(pk=firebase_project_id, is_active=True)

        fcm = FCMService(firebase_project=firebase_project)
        response = fcm.send_multicast(
            tokens=tokens,
            title=title,
            body=body,
            data=data or {},
            image_url=image_url,
            priority=priority,
        )

        # Create delivery logs for each device
        for i, device in enumerate(devices):
            individual_status = 'sent'
            error_message = None
            if hasattr(response, 'responses') and i < len(response.responses):
                if not response.responses[i].success:
                    individual_status = 'failed'
                    error_message = str(response.responses[i].exception)

            NotificationDeliveryLog.objects.update_or_create(
                notification=notification,
                device=device,
                defaults={
                    'delivered_at': timezone.now() if individual_status == 'sent' else None,
                    'status': individual_status,
                    'error_message': error_message,
                },
            )

        logger.info(
            f"Bulk async notification {notification_id}: "
            f"{response.success_count} sent, {response.failure_count} failed"
        )
        return {
            'status': 'completed',
            'success_count': response.success_count,
            'failure_count': response.failure_count,
        }

    except Exception as exc:
        logger.error(f"Bulk async notification failed: {notification_id}: {exc}")
        raise self.retry(exc=exc)


@shared_task
def send_topic_notification_async(notification_id, topic_name, firebase_project_id=None,
                                  title='', body='', data=None, image_url=''):
    """Send a topic notification asynchronously."""
    from notification.models import Notification, FirebaseProject
    from notification.services import FCMService

    try:
        firebase_project = None
        if firebase_project_id:
            firebase_project = FirebaseProject.objects.get(pk=firebase_project_id, is_active=True)

        fcm = FCMService(firebase_project=firebase_project)
        response_id = fcm.send_to_topic(
            topic=topic_name,
            title=title,
            body=body,
            data=data or {},
            image_url=image_url,
        )

        Notification.objects.filter(pk=notification_id).update(
            status='sent',
            sent_at=timezone.now(),
        )

        logger.info(f"Topic notification sent: {notification_id} -> topic '{topic_name}'")
        return {'status': 'sent', 'response': str(response_id)}

    except Exception as exc:
        Notification.objects.filter(pk=notification_id).update(status='failed')
        logger.error(f"Topic notification failed: {notification_id}: {exc}")
        raise


@shared_task
def dispatch_webhook_async(event_type, payload, api_client_id):
    """Dispatch webhook events asynchronously via Celery instead of threads."""
    from notification.models import WebhookEndpoint, ApiClient
    from notification.services.webhook_dispatcher import _deliver_webhook

    try:
        api_client = ApiClient.objects.get(pk=api_client_id)
    except ApiClient.DoesNotExist:
        return

    webhooks = WebhookEndpoint.objects.filter(
        api_client=api_client,
        is_active=True,
    )

    matching = [w for w in webhooks if event_type in (w.events or [])]

    full_payload = {
        'event': event_type,
        'timestamp': timezone.now().isoformat(),
        'data': payload,
    }

    for webhook in matching:
        _deliver_webhook(webhook, full_payload)


@shared_task
def cleanup_stale_tokens():
    """
    Periodic task: deactivate device tokens not seen in 90 days.
    Schedule via Celery Beat.
    """
    from notification.models import Device
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=90)
    stale = Device.objects.filter(is_active=True, last_seen__lt=cutoff)
    count = stale.update(is_active=False)
    logger.info(f"Deactivated {count} stale device tokens")
    return {'deactivated': count}
