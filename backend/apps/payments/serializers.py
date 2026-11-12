from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.user.full_name", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "order", "order_number", "customer_name", "transaction_id",
            "payment_gateway", "amount", "currency", "status", "paid_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "order", "transaction_id", "amount", "currency", "created_at", "updated_at"]
