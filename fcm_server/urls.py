from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from notification.views import HealthCheckView


admin.site.site_header = "Notification Server Admin"
admin.site.index_title = "Admin"


urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1 — versioned endpoints
    path('api/v1/', include('notification.urls')),

    # Backward-compatible — old /notification/ prefix still works
    path('notification/', include('notification.urls')),

    # Swagger / OpenAPI documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Auth & Health
    path('api-auth/', include('rest_framework.urls')),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
