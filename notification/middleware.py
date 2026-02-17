from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from .models import ApiClient


class ApiClientAuthentication(BaseAuthentication):
    def authenticate(self, request):
        client_id = request.headers.get("Client-ID")
        auth_token = request.headers.get("Client-Token")

        if not client_id or not auth_token:
            return None  # no authentication provided

        try:
            client = ApiClient.objects.get(client_id=client_id, auth_token=auth_token, is_active=True)
            return (client, None)  # (authenticated client, no user)
        except ApiClient.DoesNotExist:
            raise AuthenticationFailed("Invalid Client credentials")


class ApiClientAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell drf-spectacular how to document our custom auth in Swagger."""
    target_class = 'notification.middleware.ApiClientAuthentication'
    name = 'ApiClientAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Client-ID',
            'description': 'UUID of the API client (also requires Client-Token header)',
        }
