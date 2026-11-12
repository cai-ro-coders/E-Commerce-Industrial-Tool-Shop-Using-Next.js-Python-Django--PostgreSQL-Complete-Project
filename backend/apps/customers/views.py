from django.db.models import Count, Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.serializers import CustomerSerializer, UserSerializer
from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity
from apps.orders.models import Order
from apps.orders.serializers import OrderListSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    """Customer management. Non-staff can only read their own record."""

    serializer_class = CustomerSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["status"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["date_joined", "first_name", "email"]
    ordering = ["-date_joined"]

    def get_queryset(self):
        return (
            User.objects.filter(role="customer")
            .annotate(
                orders_count=Count("orders", distinct=True),
                total_spent=Sum("orders__grand_total", filter=Q(orders__payment_status="paid")),
            )
            .order_by("-date_joined")
        )

    def perform_create(self, serializer):
        customer = serializer.save(role="customer")
        log_activity(self.request.user, "customer.created", f"Created customer {customer.email}", "customer", customer.pk, self.request)

    def perform_update(self, serializer):
        customer = serializer.save(role="customer")
        log_activity(self.request.user, "customer.updated", f"Updated customer {customer.email}", "customer", customer.pk, self.request)

    def perform_destroy(self, instance):
        log_activity(self.request.user, "customer.deleted", f"Deleted customer {instance.email}", "customer", instance.pk, self.request)
        instance.delete()

    @action(detail=True, methods=["get"])
    def orders(self, request, pk=None):
        customer = self.get_object()
        orders = Order.objects.filter(user=customer).prefetch_related("items")
        return Response(
            {
                "success": True,
                "data": OrderListSerializer(orders, many=True, context={"request": request}).data,
            }
        )

    @action(detail=True, methods=["patch"])
    def toggle_status(self, request, pk=None):
        customer = self.get_object()
        customer.status = "inactive" if customer.status == "active" else "active"
        customer.is_active = customer.status == "active"
        customer.save(update_fields=["status", "is_active"])
        return Response({"success": True, "message": f"Customer {customer.status}.", "data": {"status": customer.status}})

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = self.get_queryset()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "active": qs.filter(status="active").count(),
                    "inactive": qs.exclude(status="active").count(),
                },
            }
        )
