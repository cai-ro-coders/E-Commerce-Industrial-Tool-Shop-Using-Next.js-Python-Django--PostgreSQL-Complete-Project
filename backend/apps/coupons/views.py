from decimal import Decimal, InvalidOperation

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import log_activity

from .models import Coupon
from .serializers import CouponSerializer, CouponUsageSerializer


class CouponValidateThrottle(ScopedRateThrottle):
    scope = "coupon_validate"


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.annotate(usage_count=Count("usages"))
    serializer_class = CouponSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["status", "type"]
    search_fields = ["code"]
    ordering_fields = ["created_at", "code", "value", "used_count", "end_date"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        coupon = serializer.save()
        log_activity(self.request.user, "coupon.created", f"Created coupon {coupon.code}", "coupon", coupon.pk, self.request)

    def perform_update(self, serializer):
        coupon = serializer.save()
        log_activity(self.request.user, "coupon.updated", f"Updated coupon {coupon.code}", "coupon", coupon.pk, self.request)

    def perform_destroy(self, instance):
        log_activity(self.request.user, "coupon.deleted", f"Deleted coupon {instance.code}", "coupon", instance.pk, self.request)
        instance.delete()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Coupon.objects.all()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "active": qs.filter(status="active").count(),
                    "expired": qs.filter(end_date__lt=timezone.now()).count(),
                    "total_uses": qs.aggregate(total=Sum("used_count"))["total"] or 0,
                },
            }
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        throttle_classes=[CouponValidateThrottle],
    )
    def validate(self, request):
        code = str(request.data.get("code", "")).strip().upper()
        try:
            subtotal = Decimal(str(request.data.get("subtotal", "0")))
        except (InvalidOperation, TypeError):
            subtotal = Decimal("0")
        coupon = Coupon.objects.filter(code=code).first()
        if not coupon:
            return Response({"success": False, "message": "Coupon not found."}, status=status.HTTP_404_NOT_FOUND)
        if not coupon.is_valid:
            return Response({"success": False, "message": "This coupon is expired or unavailable."}, status=status.HTTP_400_BAD_REQUEST)
        if subtotal < coupon.minimum_order:
            return Response(
                {"success": False, "message": f"Minimum order of ${coupon.minimum_order} is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        discount = coupon.calculate_discount(subtotal)
        return Response(
            {
                "success": True,
                "message": f"Coupon applied — you save ${discount}.",
                "data": {
                    "code": coupon.code,
                    "type": coupon.type,
                    "value": coupon.value,
                    "discount": discount,
                    "grand_total": max(subtotal - discount, Decimal("0")),
                },
            }
        )

    @action(detail=True, methods=["get"])
    def usages(self, request, pk=None):
        coupon = self.get_object()
        return Response(
            {
                "success": True,
                "data": CouponUsageSerializer(coupon.usages.select_related("user", "order"), many=True).data,
            }
        )
