import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


def _exponential_backoff(retries):
    """Calculate exponential backoff delay: 30s, 60s, 120s, 240s, 480s."""
    return 30 * (2 ** retries)


@shared_task(bind=True, max_retries=5)
def send_notification_async(self, notification_id, device_id, firebase_project_id=None,
                            title='', body='', data=None, image_url='', priority='high',
                            is_silent=False, click_action='', collapse_key='', actions=None):
    """
    Send a push notification to a single device asynchronously.
    Retries up to 5 times with exponential backoff.
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
            is_silent=is_silent,
            click_action=click_action or None,
            collapse_key=collapse_key or None,
            actions=actions,
        )

        NotificationDeliveryLog.objects.update_or_create(
            notification=notification,
            device=device,
            defaults={
                'delivered_at': timezone.now(),
                'status': 'sent',
            },
        )

        # Update retry count on notification
        Notification.objects.filter(pk=notification_id).update(
            retry_count=self.request.retries,
            status='sent',
            sent_at=timezone.now(),
        )

        logger.info(f"Async notification sent: {notification_id} -> device {device_id}")
        return {'status': 'sent', 'response': str(response_id)}

    except Exception as exc:
        logger.error(f"Async notification failed (attempt {self.request.retries + 1}): "
                     f"{notification_id} -> device {device_id}: {exc}")

        # Update delivery log with failure
        try:
            from notification.models import NotificationDeliveryLog
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

        # Update retry count
        try:
            from notification.models import Notification
            Notification.objects.filter(pk=notification_id).update(
                retry_count=self.request.retries + 1,
            )
            # Mark as failed if max retries exhausted
            if self.request.retries >= self.max_retries - 1:
                Notification.objects.filter(pk=notification_id).update(status='failed')
        except Exception:
            pass

        raise self.retry(exc=exc, countdown=_exponential_backoff(self.request.retries))


@shared_task(bind=True, max_retries=5)
def send_bulk_notification_async(self, notification_id, device_ids, firebase_project_id=None,
                                 title='', body='', data=None, image_url='', priority='high',
                                 is_silent=False, click_action='', collapse_key=''):
    """
    Send a push notification to multiple devices asynchronously via multicast.
    Retries with exponential backoff.
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
            is_silent=is_silent,
            click_action=click_action or None,
            collapse_key=collapse_key or None,
        )

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
        raise self.retry(exc=exc, countdown=_exponential_backoff(self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_topic_notification_async(self, notification_id, topic_name, firebase_project_id=None,
                                  title='', body='', data=None, image_url='',
                                  is_silent=False, click_action=''):
    """Send a topic notification asynchronously with exponential backoff."""
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
            is_silent=is_silent,
            click_action=click_action or None,
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
        raise self.retry(exc=exc, countdown=_exponential_backoff(self.request.retries))


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

    cutoff = timezone.now() - timedelta(days=90)
    stale = Device.objects.filter(is_active=True, last_seen__lt=cutoff)
    count = stale.update(is_active=False)
    logger.info(f"Deactivated {count} stale device tokens")
    return {'deactivated': count}


@shared_task
def process_scheduled_notifications():
    """
    Periodic task (run every minute via Celery Beat):
    Finds scheduled notifications that are due and sends them.
    Handles repeat intervals (daily, weekly, monthly).
    """
    from notification.models import (
        ScheduledNotification, Profile, Device, Notification,
        NotificationDeliveryLog, FirebaseProject,
    )
    from notification.services import FCMService, render_notification_template

    now = timezone.now()
    due = ScheduledNotification.objects.filter(
        status__in=['pending', 'active'],
        next_run_at__lte=now,
    )

    processed = 0
    for scheduled in due:
        try:
            # Resolve title/body (template or direct)
            title = scheduled.title
            body = scheduled.body
            data = scheduled.data_payload or {}

            if scheduled.template:
                rendered = render_notification_template(
                    scheduled.template,
                    scheduled.template_variables,
                )
                title = rendered['title']
                body = rendered['body']
                data = {**rendered.get('data', {}), **data}

            # Resolve Firebase project
            firebase_project = None
            if scheduled.firebase_project_id:
                firebase_project = FirebaseProject.objects.get(
                    pk=scheduled.firebase_project_id, is_active=True
                )

            fcm = FCMService(firebase_project=firebase_project)

            # Send to topic
            if scheduled.topic:
                fcm.send_to_topic(
                    topic=scheduled.topic,
                    title=title,
                    body=body,
                    data=data,
                    image_url=scheduled.image_url,
                    is_silent=scheduled.is_silent,
                    click_action=scheduled.click_action or None,
                )
            # Send to phone numbers
            elif scheduled.phone_numbers:
                profiles = Profile.objects.filter(
                    phone_number__in=scheduled.phone_numbers
                )
                devices = Device.objects.filter(
                    profile__in=profiles, is_active=True
                )
                tokens = [d.push_token for d in devices]

                if tokens:
                    notification = Notification.objects.create(
                        title=title,
                        body=body,
                        data_payload=data,
                        image_url=scheduled.image_url,
                        priority=scheduled.priority,
                        is_silent=scheduled.is_silent,
                        click_action=scheduled.click_action,
                        template=scheduled.template,
                        template_variables=scheduled.template_variables,
                        status='sent',
                        sent_at=now,
                    )

                    if len(tokens) == 1:
                        fcm.send_to_device(
                            token=tokens[0], title=title, body=body,
                            data=data, image_url=scheduled.image_url,
                            priority=scheduled.priority,
                            is_silent=scheduled.is_silent,
                            click_action=scheduled.click_action or None,
                        )
                        NotificationDeliveryLog.objects.create(
                            notification=notification,
                            device=devices[0],
                            delivered_at=now,
                            status='sent',
                        )
                    else:
                        response = fcm.send_multicast(
                            tokens=tokens, title=title, body=body,
                            data=data, image_url=scheduled.image_url,
                            priority=scheduled.priority,
                            is_silent=scheduled.is_silent,
                            click_action=scheduled.click_action or None,
                        )
                        for i, device in enumerate(devices):
                            ind_status = 'sent'
                            error_msg = None
                            if hasattr(response, 'responses') and i < len(response.responses):
                                if not response.responses[i].success:
                                    ind_status = 'failed'
                                    error_msg = str(response.responses[i].exception)
                            NotificationDeliveryLog.objects.create(
                                notification=notification,
                                device=device,
                                delivered_at=now if ind_status == 'sent' else None,
                                status=ind_status,
                                error_message=error_msg,
                            )

            # Update scheduled notification state
            scheduled.last_sent_at = now
            scheduled.occurrence_count += 1

            # Check if max occurrences reached
            if scheduled.max_occurrences and scheduled.occurrence_count >= scheduled.max_occurrences:
                scheduled.status = 'completed'
                scheduled.next_run_at = None
            elif scheduled.repeat_interval == 'none':
                scheduled.status = 'completed'
                scheduled.next_run_at = None
            else:
                scheduled.status = 'active'
                # Calculate next run
                if scheduled.repeat_interval == 'daily':
                    scheduled.next_run_at = now + timedelta(days=1)
                elif scheduled.repeat_interval == 'weekly':
                    scheduled.next_run_at = now + timedelta(weeks=1)
                elif scheduled.repeat_interval == 'monthly':
                    scheduled.next_run_at = now + timedelta(days=30)

            scheduled.save()
            processed += 1

        except Exception as e:
            logger.error(f"Failed to process scheduled notification {scheduled.pk}: {e}")
            scheduled.status = 'paused'
            scheduled.save()

    logger.info(f"Processed {processed} scheduled notifications")
    return {'processed': processed}
