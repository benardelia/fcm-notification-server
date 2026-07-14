from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiClient


def _get_client_ip(request):
    """Extract the real client IP, handling X-Forwarded-For from proxies/load balancers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class ApiClientAuthentication(BaseAuthentication):
    def authenticate(self, request):
        client_id = request.headers.get("Client-ID")
        auth_token = request.headers.get("Client-Token")

        if not client_id or not auth_token:
            return None  # no authentication provided

        try:
            client = ApiClient.objects.get(
                client_id=client_id, auth_token=auth_token, is_active=True
            )
        except ApiClient.DoesNotExist:
            raise AuthenticationFailed("Invalid Client credentials")

        # Enforce token expiry
        if not client.is_token_valid():
            raise AuthenticationFailed(
                "API token has expired. Please rotate your token."
            )

        # Enforce IP whitelist
        client_ip = _get_client_ip(request)
        if not client.is_ip_allowed(client_ip):
            raise AuthenticationFailed(
                f"Access denied: IP address '{client_ip}' is not whitelisted for this client."
            )

        return (client, None)  # (authenticated client, no auth object)


class ApiClientAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell drf-spectacular how to document our custom auth in Swagger."""

    target_class = "notification.middleware.ApiClientAuthentication"
    name = "ApiClientAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Client-ID",
            "description": "UUID of the API client (also requires Client-Token header)",
        }
