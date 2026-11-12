from rest_framework import serializers

from .models import Coupon, CouponUsage


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    usage_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "type", "type_display", "value", "minimum_order",
            "maximum_discount", "usage_limit", "used_count", "usage_count",
            "start_date", "end_date", "status", "status_display", "is_valid",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "used_count", "created_at", "updated_at"]

    def validate_code(self, value):
        value = value.upper().strip()
        qs = Coupon.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A coupon with this code already exists.")
        return value

    def validate_value(self, value):
        if value <= 0:
            raise serializers.ValidationError("Value must be greater than zero.")
        return value

    def validate(self, attrs):
        coupon_type = attrs.get("type", getattr(self.instance, "type", "percentage"))
        value = attrs.get("value", getattr(self.instance, "value", 0))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if coupon_type == "percentage" and value > 100:
            raise serializers.ValidationError({"value": "Percentage cannot exceed 100."})
        if start and end and end <= start:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        return attrs


class CouponUsageSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)

    class Meta:
        model = CouponUsage
        fields = ["id", "coupon", "coupon_code", "user", "user_name", "order", "order_number", "discount_amount", "created_at"]
