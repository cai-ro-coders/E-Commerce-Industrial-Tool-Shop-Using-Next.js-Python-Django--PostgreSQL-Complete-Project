from datetime import datetime

from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity
from apps.notifications.models import Notification
from apps.products.models import Product

from .models import InventoryLog
from .serializers import (
    InventoryAdjustSerializer,
    InventoryLogSerializer,
    StockLevelSerializer,
)


class InventoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StockLevelSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["category", "brand", "status"]
    search_fields = ["name", "sku"]
    ordering_fields = ["stock_quantity", "name", "updated_at"]
    ordering = ["stock_quantity"]

    def get_queryset(self):
        qs = Product.objects.select_related("category", "brand").prefetch_related("images")
        params = self.request.query_params
        if params.get("low_stock") == "true":
            qs = qs.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock"))
        if params.get("out_of_stock") == "true":
            qs = qs.filter(stock_quantity__lte=0)
        if params.get("stock_status") == "low_stock":
            qs = qs.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock"))
        if params.get("stock_status") == "out_of_stock":
            qs = qs.filter(stock_quantity__lte=0)
        if params.get("stock_status") == "in_stock":
            qs = qs.filter(stock_quantity__gt=F("minimum_stock"))
        return qs

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Product.objects.all()
        value = qs.aggregate(
            total=Sum(ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField()))
        )["total"] or 0
        return Response(
            {
                "success": True,
                "data": {
                    "products": qs.count(),
                    "total_units": qs.aggregate(total=Sum("stock_quantity"))["total"] or 0,
                    "low_stock": qs.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock")).count(),
                    "out_of_stock": qs.filter(stock_quantity__lte=0).count(),
                    "inventory_value": float(value),
                    "retail_value": float(
                        qs.aggregate(total=Sum(ExpressionWrapper(F("stock_quantity") * F("price"), output_field=DecimalField())))["total"] or 0
                    ),
                },
            }
        )

    @action(detail=False, methods=["get"])
    def valuation(self, request):
        categories = (
            Product.objects.values("category__name")
            .annotate(
                units=Sum("stock_quantity"),
                cost_value=Sum(ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField())),
                retail_value=Sum(ExpressionWrapper(F("stock_quantity") * F("price"), output_field=DecimalField())),
            )
            .order_by("-cost_value")
        )
        return Response({"success": True, "data": list(categories)})

    @action(detail=False, methods=["get"])
    def low_stock(self, request):
        qs = Product.objects.filter(stock_quantity__lte=F("minimum_stock")).select_related("category").prefetch_related("images")[:50]
        return Response({"success": True, "data": StockLevelSerializer(qs, many=True, context={"request": request}).data})

    @action(detail=False, methods=["get"])
    def calendar(self, request):
        events = []
        logs = InventoryLog.objects.select_related("product").filter(
            Q(scheduled_date__isnull=False) | Q(created_at__gte=timezone.now() - timezone.timedelta(days=30))
        )[:300]
        colors = {"stock_in": "#16a34a", "stock_out": "#dc2626", "adjustment": "#f59e0b", "return": "#2563eb"}
        for log in logs:
            start = log.scheduled_date or timezone.localtime(log.created_at).date()
            events.append(
                {
                    "id": f"log-{log.id}",
                    "title": f"{log.get_type_display()}: {log.product.sku} × {log.quantity}",
                    "start": start.isoformat(),
                    "backgroundColor": colors.get(log.type, "#64748b"),
                    "borderColor": colors.get(log.type, "#64748b"),
                    "extendedProps": {
                        "type": log.type,
                        "quantity": log.quantity,
                        "product": log.product.name,
                        "reference": log.reference,
                        "remarks": log.remarks,
                    },
                }
            )
        low_stock = Product.objects.filter(stock_quantity__lte=F("minimum_stock"))[:20]
        for product in low_stock:
            events.append(
                {
                    "id": f"low-{product.id}",
                    "title": f"Reorder: {product.name} ({product.stock_quantity} left)",
                    "start": timezone.localdate().isoformat(),
                    "backgroundColor": "#dc2626",
                    "borderColor": "#dc2626",
                    "extendedProps": {"type": "low_stock", "product": product.name},
                }
            )
        return Response({"success": True, "data": events})


class InventoryLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryLog.objects.select_related("product", "created_by")
    serializer_class = InventoryLogSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["type", "product"]
    search_fields = ["product__name", "product__sku", "reference", "remarks"]
    ordering_fields = ["created_at", "quantity"]
    ordering = ["-created_at"]


class InventoryAdjustView(APIView):
    permission_classes = [IsAdminOrStaff]

    @transaction.atomic
    def post(self, request):
        serializer = InventoryAdjustSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Invalid adjustment.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        product = Product.objects.select_for_update().get(pk=data["product"].pk)
        kind = data["type"]
        quantity = data["quantity"]
        previous = product.stock_quantity
        if kind in ("stock_in", "return"):
            product.stock_quantity += quantity
        elif kind == "stock_out":
            if quantity > product.stock_quantity:
                raise ValidationError({"quantity": "Insufficient stock."})
            product.stock_quantity -= quantity
        else:
            product.stock_quantity = quantity
        product.save(update_fields=["stock_quantity"])

        log = InventoryLog.objects.create(
            product=product,
            type=kind,
            quantity=quantity,
            reference=data.get("reference", ""),
            remarks=data.get("remarks", ""),
            scheduled_date=data.get("scheduled_date"),
            created_by=request.user,
        )
        if product.stock_quantity <= product.minimum_stock:
            Notification.objects.create(
                user=None,
                title="Low stock alert",
                message=f"{product.name} ({product.sku}) has {product.stock_quantity} units left.",
                type="stock",
                link=f"/admin/products/{product.pk}",
            )
        log_activity(
            request.user,
            "inventory.adjusted",
            f"{kind} {quantity} for {product.sku} ({previous} -> {product.stock_quantity})",
            "inventory",
            log.pk,
            request,
        )
        return Response(
            {
                "success": True,
                "message": f"Stock updated: {previous} → {product.stock_quantity}.",
                "data": {
                    "log": InventoryLogSerializer(log, context={"request": request}).data,
                    "product": StockLevelSerializer(product, context={"request": request}).data,
                },
            },
            status=status.HTTP_201_CREATED,
        )
