from django.urls import path
from .views import *

urlpatterns = [
    path('notify/', SendNotificationView.as_view(), name='send-notification'),
    path('profile/', ProfileListCreateView.as_view(), name='profile-list-create'),
    path('profile/<int:pk>/', ProfileRetrieveUpdateDestroyView.as_view(), name='profile-detail'),
    path('device/', DeviceListCreateView.as_view(), name='device-list-create'),
    path('device/<int:pk>/', DeviceRetrieveUpdateDestroyView.as_view(), name='device-detail'),
    path('notification/', NotificationListCreateView.as_view(), name='notification-list-create'),
    path('notification/<int:pk>/', NotificationRetrieveUpdateDestroyView.as_view(), name='notification-detail'),
    path('notificationDeliveryLog/', NotificationDeliveryLogListCreateView.as_view(), name='notificationDeliveryLog-list-create'),
    path('notificationDeliveryLog/<int:pk>/', NotificationDeliveryLogRetrieveUpdateDestroyView.as_view(), name='notificationDeliveryLog-detail'),
    path('topic/', TopicListCreateView.as_view(), name='topic-list-create'),
    path('topic/<int:pk>/', TopicRetrieveUpdateDestroyView.as_view(), name='topic-detail'),
    path('user-topic/', UserTopicListCreateView.as_view(), name='user-topic-list-create'),
    path('user-topic/<int:pk>/', UserTopicRetrieveUpdateDestroyView.as_view(), name='user-topic-detail'),
]
