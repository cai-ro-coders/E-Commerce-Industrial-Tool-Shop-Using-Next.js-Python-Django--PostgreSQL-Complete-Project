from django.db.models import Count, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import FileDocument, Setting
from apps.core.permissions import IsAdminOrStaff, IsAdminOrStaffOrReadOnly
from apps.core.serializers import (
    FileDocumentSerializer,
    PublicSettingSerializer,
    SettingSerializer,
)
from apps.core.utils import log_activity


class SettingViewSet(viewsets.ModelViewSet):
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    permission_classes = [IsAdminOrStaffOrReadOnly]
    filterset_fields = ["group"]
    search_fields = ["key", "value"]
    ordering_fields = ["key", "group", "updated_at"]
    ordering = ["group", "key"]

    def get_permissions(self):
        if self.action in ("public",):
            return []
        return super().get_permissions()

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "setting.created", f"Created setting {obj.key}", "setting", obj.pk, self.request)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "setting.updated", f"Updated setting {obj.key}", "setting", obj.pk, self.request)

    def perform_destroy(self, instance):
        log_activity(self.request.user, "setting.deleted", f"Deleted setting {instance.key}", "setting", instance.pk, self.request)
        instance.delete()

    @action(detail=False, methods=["get"], permission_classes=[])
    def public(self, request):
        qs = Setting.objects.exclude(group__in=["payment", "smtp", "backup"])
        return Response({"success": True, "data": PublicSettingSerializer(qs, many=True).data})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminOrStaff])
    def bulk_update(self, request):
        payload = request.data if isinstance(request.data, list) else request.data.get("settings", [])
        updated = 0
        for item in payload:
            key = item.get("key")
            if not key:
                continue
            Setting.objects.update_or_create(
                key=key,
                defaults={
                    "value": item.get("value", ""),
                    "group": item.get("group", "general"),
                },
            )
            updated += 1
        log_activity(request.user, "setting.updated", f"Bulk updated {updated} settings", "setting", "", request)
        return Response({"success": True, "message": f"{updated} settings saved.", "data": {"updated": updated}})


class FileDocumentViewSet(viewsets.ModelViewSet):
    queryset = FileDocument.objects.select_related("uploaded_by")
    serializer_class = FileDocumentSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["category"]
    search_fields = ["name", "description", "content_type"]
    ordering_fields = ["created_at", "name", "size"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        obj = serializer.save()
        log_activity(self.request.user, "file.uploaded", f"Uploaded {obj.name}", "file", obj.pk, self.request)

    def perform_destroy(self, instance):
        instance.file.delete(save=False)
        log_activity(self.request.user, "file.deleted", f"Deleted {instance.name}", "file", instance.pk, self.request)
        instance.delete()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = self.get_queryset()
        by_category = qs.values("category").annotate(count=Count("id"), size=Sum("size"))
        return Response(
            {
                "success": True,
                "data": {
                    "total_files": qs.count(),
                    "total_size": qs.aggregate(total=Sum("size"))["total"] or 0,
                    "by_category": list(by_category),
                },
            }
        )
