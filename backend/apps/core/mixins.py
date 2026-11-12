from rest_framework import status
from rest_framework.response import Response


class EnvelopeListMixin:
    """Return unpaginated list responses in the standard ``{success, data}`` envelope."""

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response({"success": True, "data": serializer.data})


class EnvelopeCreateMixin:
    """Wrap create responses in the standard ``{success, message, data}`` envelope."""

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"success": True, "message": "Created successfully.", "data": serializer.data},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
