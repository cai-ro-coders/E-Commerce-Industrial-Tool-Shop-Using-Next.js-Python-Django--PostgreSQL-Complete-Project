import csv
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity
from apps.inventory.models import InventoryLog
from apps.notifications.models import Notification

from .models import Order, OrderStatusHistory
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderStatusHistorySerializer,
    OrderUpdateSerializer,
)


def is_staff(user):
    return user.is_authenticated and (user.role in ("admin", "staff") or user.is_superuser)


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filterset_fields = ["order_status", "payment_status", "payment_method"]
    search_fields = ["order_number", "user__email", "user__first_name", "user__last_name", "tracking_number"]
    ordering_fields = ["created_at", "grand_total", "order_status", "payment_status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        if self.action == "create":
            return OrderCreateSerializer
        if self.action in ("update", "partial_update"):
            return OrderUpdateSerializer
        return OrderDetailSerializer

    def get_queryset(self):
        qs = Order.objects.select_related("user", "shipping_address", "coupon").prefetch_related(
            "items__product__images", "payments", "status_history"
        )
        if not is_staff(self.request.user):
            qs = qs.filter(user=self.request.user)
        params = self.request.query_params
        if params.get("user"):
            qs = qs.filter(user_id=params["user"])
        if params.get("date_from"):
            qs = qs.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(created_at__date__lte=params["date_to"])
        return qs

    def get_permissions(self):
        if self.action in ("stats", "export"):
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Please check your order details.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order = serializer.save()
        log_activity(request.user, "order.created", f"Placed order {order.order_number}", "order", order.pk, request)
        return Response(
            {
                "success": True,
                "message": f"Order {order.order_number} placed successfully.",
                "data": OrderDetailSerializer(order, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if not is_staff(request.user):
            raise PermissionDenied("Only staff can update orders.")
        old_status = order.order_status
        serializer = self.get_serializer(order, data=request.data, partial=kwargs.get("partial", False))
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Please check the form.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        with transaction.atomic():
            if "shipping_address_id" in data:
                from apps.accounts.models import Address

                address_id = data.pop("shipping_address_id")
                order.shipping_address = Address.objects.filter(pk=address_id).first() if address_id else None
            for key, value in data.items():
                setattr(order, key, value)
            new_status = order.order_status
            now = timezone.now()
            if new_status != old_status:
                self._apply_status_side_effects(order, old_status, new_status, now, request.user)
            order.save()
            OrderStatusHistory.objects.create(
                order=order,
                status=order.order_status,
                note=request.data.get("note", "Order updated"),
                created_by=request.user,
            )
            if order.payment_status == "paid":
                order.payments.filter(status="pending").update(status="paid", paid_at=now)
        log_activity(request.user, "order.updated", f"Updated order {order.order_number}", "order", order.pk, request)
        return Response(
            {
                "success": True,
                "message": "Order updated.",
                "data": OrderDetailSerializer(order, context={"request": request}).data,
            }
        )

    def _apply_status_side_effects(self, order, old_status, new_status, now, user):
        if new_status == "shipped":
            order.shipped_at = order.shipped_at or now
        elif new_status == "delivered":
            order.delivered_at = order.delivered_at or now
        elif new_status == "cancelled":
            order.cancelled_at = now
            self._restock(order, user, "Order cancelled", old_status)
            if order.payment_status == "paid":
                order.payment_status = "refunded"
                order.payments.filter(status="paid").update(status="refunded")
        elif new_status == "returned":
            self._restock(order, user, "Order returned", old_status)
        Notification.objects.create(
            user=order.user,
            title=f"Order {order.order_number} {new_status}",
            message=f"Your order status is now {new_status}.",
            type="order",
            link=f"/orders/{order.pk}",
        )

    def _restock(self, order, user, reason, old_status):
        if old_status in ("cancelled", "returned"):
            return
        for item in order.items.select_related("product"):
            if not item.product:
                continue
            item.product.stock_quantity += item.quantity
            item.product.save(update_fields=["stock_quantity"])
            InventoryLog.objects.create(
                product=item.product,
                type="return",
                quantity=item.quantity,
                reference=order.order_number,
                remarks=reason,
                created_by=user if getattr(user, "is_authenticated", False) else None,
            )

    def destroy(self, request, *args, **kwargs):
        if not is_staff(request.user):
            raise PermissionDenied("Only staff can delete orders.")
        order = self.get_object()
        log_activity(request.user, "order.deleted", f"Deleted order {order.order_number}", "order", order.pk, request)
        order.delete()
        return Response({"success": True, "message": "Order deleted."})

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        if not is_staff(request.user):
            raise PermissionDenied("Only staff can update orders.")
        order = self.get_object()
        new_status = request.data.get("order_status") or request.data.get("status")
        valid = [s[0] for s in Order.Status.choices]
        if new_status not in valid:
            raise ValidationError({"order_status": f"Invalid status. Choose from {', '.join(valid)}."})
        old_status = order.order_status
        tracking = request.data.get("tracking_number")
        note = request.data.get("note", "")
        with transaction.atomic():
            if tracking is not None:
                order.tracking_number = tracking
            if new_status in ("shipped", "delivered") and not (tracking or order.tracking_number):
                raise ValidationError({"tracking_number": "Tracking number is required."})
            order.order_status = new_status
            self._apply_status_side_effects(order, old_status, new_status, timezone.now(), request.user)
            order.save()
            OrderStatusHistory.objects.create(
                order=order, status=new_status, note=note or f"Status changed to {new_status}", created_by=request.user
            )
        log_activity(request.user, "order.status_changed", f"{order.order_number} -> {new_status}", "order", order.pk, request)
        return Response(
            {
                "success": True,
                "message": f"Order marked as {new_status}.",
                "data": OrderDetailSerializer(order, context={"request": request}).data,
            }
        )

    @action(detail=True, methods=["patch"], url_path="payment")
    def update_payment(self, request, pk=None):
        if not is_staff(request.user):
            raise PermissionDenied("Only staff can update payments.")
        order = self.get_object()
        payment_status = request.data.get("payment_status")
        if payment_status not in [s[0] for s in Order.PaymentStatus.choices]:
            raise ValidationError({"payment_status": "Invalid payment status."})
        order.payment_status = payment_status
        order.save(update_fields=["payment_status"])
        if payment_status == "paid":
            order.payments.filter(status="pending").update(status="paid", paid_at=timezone.now())
        elif payment_status == "refunded":
            order.payments.update(status="refunded")
        elif payment_status == "failed":
            order.payments.filter(status="pending").update(status="failed")
        log_activity(request.user, "order.payment_changed", f"{order.order_number} payment -> {payment_status}", "order", order.pk, request)
        return Response({"success": True, "message": "Payment status updated.", "data": {"payment_status": payment_status}})

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        order = self.get_object()
        return Response(
            {
                "success": True,
                "data": OrderStatusHistorySerializer(order.status_history.all(), many=True).data,
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Order.objects.all()
        paid = qs.filter(payment_status="paid")
        revenue = paid.aggregate(total=Sum("grand_total"))["total"] or 0
        count = qs.count()
        cost = paid.aggregate(
            total=Sum(
                ExpressionWrapper(F("items__cost_price") * F("items__quantity"), output_field=DecimalField())
            )
        )["total"] or 0
        return Response(
            {
                "success": True,
                "data": {
                    "total_orders": count,
                    "open_orders": qs.filter(order_status__in=["pending", "processing"]).count(),
                    "paid_orders": paid.count(),
                    "total_revenue": float(revenue),
                    "net_earning": float(revenue) - float(cost),
                    "average_order_value": round(float(revenue) / paid.count(), 2) if paid.count() else 0,
                    "today_orders": qs.filter(created_at__date=timezone.localdate()).count(),
                    "status_breakdown": list(qs.values("order_status").annotate(count=Count("id"))),
                },
            }
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        qs = self.get_queryset() if is_staff(request.user) else Order.objects.filter(user=request.user)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Order", "Customer", "Email", "Date", "Items", "Subtotal", "Discount",
            "Shipping", "Tax", "Grand Total", "Payment Method", "Payment Status",
            "Order Status", "Tracking",
        ])
        for o in qs:
            writer.writerow([
                o.order_number, o.user.full_name, o.user.email,
                o.created_at.strftime("%Y-%m-%d %H:%M"), o.item_count, o.subtotal,
                o.discount, o.shipping_fee, o.tax, o.grand_total,
                o.payment_method, o.payment_status, o.order_status, o.tracking_number,
            ])
        log_activity(request.user, "order.exported", "Exported orders CSV", "order", "", request)
        return response
