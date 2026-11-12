from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrStaffOrReadOnly
from apps.core.utils import log_activity

from .models import Brand
from .serializers import BrandSerializer


class BrandViewSet(viewsets.ModelViewSet):
    serializer_class = BrandSerializer
    permission_classes = [IsAdminOrStaffOrReadOnly]
    filterset_fields = ["status"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        return Brand.objects.annotate(product_count=Count("products", distinct=True))

    def perform_create(self, serializer):
        brand = serializer.save()
        log_activity(self.request.user, "brand.created", f"Created brand {brand.name}", "brand", brand.pk, self.request)

    def perform_update(self, serializer):
        brand = serializer.save()
        log_activity(self.request.user, "brand.updated", f"Updated brand {brand.name}", "brand", brand.pk, self.request)

    def perform_destroy(self, instance):
        log_activity(self.request.user, "brand.deleted", f"Deleted brand {instance.name}", "brand", instance.pk, self.request)
        instance.delete()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Brand.objects.all()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "active": qs.filter(status="active").count(),
                    "inactive": qs.filter(status="inactive").count(),
                },
            }
        )
