from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Return consistent, human-readable API errors."""
    if isinstance(exc, DjangoValidationError):
        message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
        return Response(
            {"success": False, "message": message, "errors": {"detail": message}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "success": False,
                "message": "A record with these details already exists.",
                "errors": {"detail": "Integrity constraint violated."},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict):
        if "detail" in detail:
            message = str(detail["detail"])
        else:
            first_key = next(iter(detail))
            first_val = detail[first_key]
            if isinstance(first_val, (list, tuple)) and first_val:
                message = f"{first_key}: {first_val[0]}"
            else:
                message = f"{first_key}: {first_val}"
    elif isinstance(detail, (list, tuple)) and detail:
        message = str(detail[0])

    response.data = {"success": False, "message": message, "errors": detail}
    return response
