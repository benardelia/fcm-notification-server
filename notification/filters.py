import django_filters
from .models import (
    Profile, Device, Notification, NotificationDeliveryLog,
    Topic, NotificationTemplate, NotificationAnalytics,
    ScheduledNotification,
)


class ProfileFilter(django_filters.FilterSet):
    phone_number = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Profile
        fields = ['phone_number', 'is_active']


class DeviceFilter(django_filters.FilterSet):
    profile = django_filters.NumberFilter()
    device_type = django_filters.ChoiceFilter(choices=Device.DEVICE_TYPES)
    app_version = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Device
        fields = ['profile', 'device_type', 'is_active', 'app_version']


class NotificationFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Notification.STATUS_CHOICES)
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    title = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Notification
        fields = ['status', 'title']


class DeliveryLogFilter(django_filters.FilterSet):
    notification = django_filters.NumberFilter()
    device = django_filters.NumberFilter()
    status = django_filters.ChoiceFilter(choices=NotificationDeliveryLog.STATUS_CHOICES)

    class Meta:
        model = NotificationDeliveryLog
        fields = ['notification', 'device', 'status']


class TopicFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Topic
        fields = ['name']


class NotificationTemplateFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = NotificationTemplate
        fields = ['name', 'is_active']


class ScheduledNotificationFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=ScheduledNotification.STATUS_CHOICES)
    repeat_interval = django_filters.ChoiceFilter(choices=ScheduledNotification.REPEAT_CHOICES)
    scheduled_after = django_filters.DateTimeFilter(field_name='scheduled_at', lookup_expr='gte')
    scheduled_before = django_filters.DateTimeFilter(field_name='scheduled_at', lookup_expr='lte')
    topic = django_filters.CharFilter(lookup_expr='icontains')
    title = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = ScheduledNotification
        fields = ['status', 'repeat_interval', 'topic']


class AnalyticsFilter(django_filters.FilterSet):
    date = django_filters.DateFilter()
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    platform = django_filters.CharFilter()

    class Meta:
        model = NotificationAnalytics
        fields = ['date', 'platform']
