from django.urls import path
from .views import (
    SendNotificationView, BulkSendNotificationView, TopicNotificationView,
    TemplateSendView,
    ProfileListCreateView, ProfileRetrieveUpdateDestroyView,
    DeviceListCreateView, DeviceRetrieveUpdateDestroyView,
    NotificationListCreateView, NotificationRetrieveUpdateDestroyView,
    NotificationDeliveryLogListCreateView, NotificationDeliveryLogRetrieveUpdateDestroyView,
    TopicListCreateView, TopicRetrieveUpdateDestroyView,
    UserTopicListCreateView, UserTopicRetrieveUpdateDestroyView,
    FirebaseProjectListCreateView, FirebaseProjectRetrieveUpdateDestroyView,
    NotificationTemplateListCreateView, NotificationTemplateRetrieveUpdateDestroyView,
    WebhookEndpointListCreateView, WebhookEndpointRetrieveUpdateDestroyView,
    NotificationAnalyticsListView,
    ScheduledNotificationListCreateView, ScheduledNotificationRetrieveUpdateDestroyView,
)

urlpatterns = [
    # --- Notification Sending ---
    path('notify/', SendNotificationView.as_view(), name='send-notification'),
    path('notify/bulk/', BulkSendNotificationView.as_view(), name='bulk-send-notification'),
    path('notify/topic/', TopicNotificationView.as_view(), name='topic-notification'),
    path('notify/template/', TemplateSendView.as_view(), name='template-send'),

    # --- Scheduled Notifications ---
    path('scheduled/', ScheduledNotificationListCreateView.as_view(), name='scheduled-list-create'),
    path('scheduled/<int:pk>/', ScheduledNotificationRetrieveUpdateDestroyView.as_view(), name='scheduled-detail'),

    # --- Profiles ---
    path('profile/', ProfileListCreateView.as_view(), name='profile-list-create'),
    path('profile/<int:pk>/', ProfileRetrieveUpdateDestroyView.as_view(), name='profile-detail'),

    # --- Devices ---
    path('device/', DeviceListCreateView.as_view(), name='device-list-create'),
    path('device/<int:pk>/', DeviceRetrieveUpdateDestroyView.as_view(), name='device-detail'),

    # --- Notifications ---
    path('notification/', NotificationListCreateView.as_view(), name='notification-list-create'),
    path('notification/<int:pk>/', NotificationRetrieveUpdateDestroyView.as_view(), name='notification-detail'),

    # --- Delivery Logs ---
    path('delivery-log/', NotificationDeliveryLogListCreateView.as_view(), name='delivery-log-list-create'),
    path('delivery-log/<int:pk>/', NotificationDeliveryLogRetrieveUpdateDestroyView.as_view(), name='delivery-log-detail'),

    # --- Topics ---
    path('topic/', TopicListCreateView.as_view(), name='topic-list-create'),
    path('topic/<int:pk>/', TopicRetrieveUpdateDestroyView.as_view(), name='topic-detail'),

    # --- User Topics ---
    path('user-topic/', UserTopicListCreateView.as_view(), name='user-topic-list-create'),
    path('user-topic/<int:pk>/', UserTopicRetrieveUpdateDestroyView.as_view(), name='user-topic-detail'),

    # --- Configuration: Firebase Projects ---
    path('firebase-projects/', FirebaseProjectListCreateView.as_view(), name='firebase-project-list-create'),
    path('firebase-projects/<int:pk>/', FirebaseProjectRetrieveUpdateDestroyView.as_view(), name='firebase-project-detail'),

    # --- Configuration: Notification Templates ---
    path('templates/', NotificationTemplateListCreateView.as_view(), name='template-list-create'),
    path('templates/<int:pk>/', NotificationTemplateRetrieveUpdateDestroyView.as_view(), name='template-detail'),

    # --- Configuration: Webhooks ---
    path('webhooks/', WebhookEndpointListCreateView.as_view(), name='webhook-list-create'),
    path('webhooks/<int:pk>/', WebhookEndpointRetrieveUpdateDestroyView.as_view(), name='webhook-detail'),

    # --- Analytics ---
    path('analytics/', NotificationAnalyticsListView.as_view(), name='analytics-list'),
]
