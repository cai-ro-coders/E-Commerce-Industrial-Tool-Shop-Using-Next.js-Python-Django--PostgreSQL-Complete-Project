from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrStaffOrReadOnly
from apps.core.utils import log_activity

from .models import Category
from .serializers import CategorySerializer, CategoryTreeSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrStaffOrReadOnly]
    filterset_fields = ["status", "parent"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        qs = Category.objects.select_related("parent").annotate(
            product_count=Count("products", distinct=True)
        )
        if self.request.query_params.get("roots") == "true":
            qs = qs.filter(parent__isnull=True)
        return qs

    def perform_create(self, serializer):
        category = serializer.save()
        log_activity(self.request.user, "category.created", f"Created category {category.name}", "category", category.pk, self.request)

    def perform_update(self, serializer):
        category = serializer.save()
        log_activity(self.request.user, "category.updated", f"Updated category {category.name}", "category", category.pk, self.request)

    def perform_destroy(self, instance):
        if instance.products.exists():
            from rest_framework.exceptions import ValidationError

            raise ValidationError("Cannot delete a category that still has products.")
        log_activity(self.request.user, "category.deleted", f"Deleted category {instance.name}", "category", instance.pk, self.request)
        instance.delete()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Category.objects.all()
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

    @action(detail=False, methods=["get"])
    def tree(self, request):
        qs = (
            Category.objects.filter(parent__isnull=True)
            .prefetch_related("children")
            .annotate(product_count=Count("products", distinct=True))
        )
        return Response(
            {
                "success": True,
                "data": CategoryTreeSerializer(qs, many=True, context={"request": request}).data,
            }
        )
