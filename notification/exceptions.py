from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError


def custom_exception_handler(exc, context):
    """
    Consistent error response format for all API errors.

    Response format:
    {
        "success": false,
        "error": {
            "code": "validation_error",
            "message": "Human readable message",
            "details": { ... }  // optional field-level errors
        }
    }
    """
    # Let DRF handle it first
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exceptions
        if isinstance(exc, DjangoValidationError):
            return Response({
                'success': False,
                'error': {
                    'code': 'validation_error',
                    'message': 'Validation failed.',
                    'details': exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages},
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Let other unhandled exceptions bubble up (500s handled by Django)
        return None

    # Map DRF exceptions to consistent format
    error_data = {
        'success': False,
        'error': {
            'code': _get_error_code(response.status_code),
            'message': _get_error_message(response),
            'details': _get_error_details(response),
        }
    }

    response.data = error_data
    return response


def _get_error_code(status_code):
    """Map HTTP status codes to error code strings."""
    codes = {
        400: 'bad_request',
        401: 'authentication_failed',
        403: 'permission_denied',
        404: 'not_found',
        405: 'method_not_allowed',
        429: 'throttled',
        500: 'server_error',
    }
    return codes.get(status_code, 'error')


def _get_error_message(response):
    """Extract a human-readable message from the response data."""
    data = response.data

    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # Field validation errors — summarize
        errors = []
        for field, messages in data.items():
            if isinstance(messages, list):
                errors.append(f"{field}: {', '.join(str(m) for m in messages)}")
            else:
                errors.append(f"{field}: {messages}")
        if errors:
            return '; '.join(errors)

    if isinstance(data, list):
        return '; '.join(str(item) for item in data)

    return str(data)


def _get_error_details(response):
    """Return field-level error details for validation errors, or None."""
    data = response.data

    if isinstance(data, dict) and 'detail' not in data:
        # Field-level validation errors
        return data

    return None
