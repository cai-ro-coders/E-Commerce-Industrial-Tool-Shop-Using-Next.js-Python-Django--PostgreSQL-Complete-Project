from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.mixins import EnvelopeListMixin
from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity

from .models import Notification
from .serializers import NotificationSerializer


def is_staff(user):
    return user.is_authenticated and (user.role in ("admin", "staff") or user.is_superuser)


class NotificationViewSet(EnvelopeListMixin, viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if is_staff(user):
            # Staff see their own notifications and system broadcasts
            return Notification.objects.filter(Q(user=user) | Q(user__isnull=True))
        return Notification.objects.filter(user=user)

    def get_permissions(self):
        if self.action == "create":
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            notification = serializer.save(user=None)
            log_activity(request.user, "notification.sent", f"Broadcast: {notification.title}", "notification", notification.pk, request)
            return Response({"success": True, "message": "Notification sent.", "data": serializer.data}, status=201)
        return Response({"success": False, "message": "Invalid notification.", "errors": serializer.errors}, status=400)

    @action(detail=True, methods=["patch"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response({"success": True, "message": "Marked as read."})

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({"success": True, "message": "All notifications marked as read."})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        return Response({"success": True, "data": {"count": self.get_queryset().filter(is_read=False).count()}})
