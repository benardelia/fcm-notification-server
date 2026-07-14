"""
Custom DRF throttle classes for per-endpoint rate limiting.

Rate limits are configured in settings.py under REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']:
    - api_client:         200/minute  (default for all authenticated requests)
    - send_notification:  100/minute  (single send endpoint)
    - bulk_send:          10/minute   (bulk send endpoint)
    - device_registration: 50/minute  (device register endpoint)
    - analytics:          30/minute   (analytics endpoint)
"""

from rest_framework.throttling import SimpleRateThrottle


class ApiClientRateThrottle(SimpleRateThrottle):
    """
    Default throttle applied to all authenticated API client requests.
    Uses the ApiClient's client_id as the unique key so each client gets
    its own rate limit bucket.
    """

    scope = "api_client"

    def get_cache_key(self, request, view):
        if not hasattr(request.user, "client_id"):
            return None  # Not an ApiClient — don't throttle
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.client_id),
        }


class SendNotificationThrottle(SimpleRateThrottle):
    """
    Stricter throttle for the single send notification endpoint.
    Applied in addition to the default api_client throttle.
    """

    scope = "send_notification"

    def get_cache_key(self, request, view):
        if not hasattr(request.user, "client_id"):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.client_id),
        }


class BulkSendThrottle(SimpleRateThrottle):
    """
    Throttle for bulk send endpoint — much lower limit (10/minute)
    as each call can send to hundreds of devices.
    """

    scope = "bulk_send"

    def get_cache_key(self, request, view):
        if not hasattr(request.user, "client_id"):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.client_id),
        }


class DeviceRegistrationThrottle(SimpleRateThrottle):
    """Throttle for device registration endpoint."""

    scope = "device_registration"

    def get_cache_key(self, request, view):
        if not hasattr(request.user, "client_id"):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.client_id),
        }


class AnalyticsThrottle(SimpleRateThrottle):
    """Throttle for analytics endpoints."""

    scope = "analytics"

    def get_cache_key(self, request, view):
        if not hasattr(request.user, "client_id"):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": str(request.user.client_id),
        }
