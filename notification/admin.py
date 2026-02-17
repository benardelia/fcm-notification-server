from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Profile)
admin.site.register(Device)
admin.site.register(Notification)
admin.site.register(UserTopic)
admin.site.register(Topic)
admin.site.register(NotificationDeliveryLog)
admin.site.register(ApiClient)
admin.site.register(FirebaseProject)
admin.site.register(NotificationTemplate)
admin.site.register(NotificationAnalytics)
admin.site.register(WebhookEndpoint)
admin.site.register(ScheduledNotification)