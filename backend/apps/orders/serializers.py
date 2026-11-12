from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Address
from apps.cart.models import Cart
from apps.core.utils import get_setting
from apps.coupons.models import Coupon, CouponUsage
from apps.inventory.models import InventoryLog
from apps.notifications.models import Notification
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer
from apps.products.models import Product

from .models import Order, OrderItem, OrderStatusHistory


class OrderItemSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    product_slug = serializers.CharField(source="product.slug", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = [
            "id", "product", "product_slug", "product_name", "sku", "quantity",
            "price", "cost_price", "total", "image",
        ]

    def get_image(self, obj):
        if obj.product:
            image = obj.product.primary_image
            if image and image.image:
                request = self.context.get("request")
                return request.build_absolute_uri(image.image.url) if request else image.image.url
        return None


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OrderStatusHistory
        fields = ["id", "status", "note", "created_by", "created_by_name", "created_at"]

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else "System"


class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="user.full_name", read_only=True)
    customer_email = serializers.CharField(source="user.email", read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    first_item_image = serializers.SerializerMethodField()
    items_preview = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "customer_name", "customer_email", "subtotal",
            "discount", "shipping_fee", "tax", "grand_total", "payment_method",
            "payment_status", "order_status", "item_count", "first_item_image",
            "items_preview", "created_at", "updated_at",
        ]

    def get_first_item_image(self, obj):
        item = obj.items.first()
        if item and item.product:
            image = item.product.primary_image
            if image and image.image:
                request = self.context.get("request")
                return request.build_absolute_uri(image.image.url) if request else image.image.url
        return None

    def get_items_preview(self, obj):
        return [f"{i.product_name} × {i.quantity}" for i in obj.items.all()[:3]]


class OrderDetailSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="user.full_name", read_only=True)
    customer_email = serializers.CharField(source="user.email", read_only=True)
    customer_phone = serializers.CharField(source="user.phone", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    shipping_address_detail = serializers.SerializerMethodField()
    coupon_code = serializers.CharField(source="coupon.code", read_only=True, default=None)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "user", "customer_name", "customer_email",
            "customer_phone", "subtotal", "discount", "shipping_fee", "tax",
            "grand_total", "payment_method", "payment_status", "order_status",
            "shipping_address", "shipping_address_detail", "coupon", "coupon_code",
            "notes", "tracking_number", "shipped_at", "delivered_at",
            "cancelled_at", "items", "payments", "status_history", "item_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "order_number", "user", "created_at", "updated_at"]

    def get_shipping_address_detail(self, obj):
        if not obj.shipping_address:
            return None
        address = obj.shipping_address
        return {
            "id": address.id,
            "full_name": address.full_name,
            "phone": address.phone,
            "address_line_1": address.address_line_1,
            "address_line_2": address.address_line_2,
            "city": address.city,
            "province": address.province,
            "postal_code": address.postal_code,
            "country": address.country,
            "formatted": address.formatted,
        }


class OrderCreateSerializer(serializers.Serializer):
    shipping_address_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices, default="cod")
    coupon_code = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_shipping_address_id(self, value):
        user = self.context["request"].user
        qs = Address.objects.filter(pk=value)
        if user.role not in ("admin", "staff"):
            qs = qs.filter(user=user)
        if not qs.exists():
            raise serializers.ValidationError("Shipping address not found.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        cart = Cart.objects.filter(user=user).prefetch_related("items__product").first()
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty.")
        for item in cart.items.all():
            if item.product.status != "active":
                raise serializers.ValidationError(f"{item.product.name} is no longer available.")
            if item.product.stock_quantity < item.quantity:
                raise serializers.ValidationError(
                    f"Only {item.product.stock_quantity} units of {item.product.name} remain."
                )
        attrs["cart"] = cart
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        cart = validated_data["cart"]
        items = list(cart.items.select_related("product").all())

        subtotal = sum((item.price * item.quantity for item in items), Decimal("0"))
        discount = Decimal("0")
        coupon = None
        code = (validated_data.get("coupon_code") or "").strip().upper()
        if code:
            coupon = Coupon.objects.filter(code=code).first()
            if coupon and coupon.is_valid:
                discount = coupon.calculate_discount(subtotal)
            else:
                coupon = None

        try:
            shipping_fee = Decimal(str(get_setting("shipping_fee", "15")))
        except Exception:
            shipping_fee = Decimal("15")
        try:
            tax_rate = Decimal(str(get_setting("tax_rate", "0")))
        except Exception:
            tax_rate = Decimal("0")
        tax = ((subtotal - discount) * tax_rate / Decimal("100")).quantize(Decimal("0.01"))
        grand_total = subtotal - discount + shipping_fee + tax

        address = Address.objects.get(pk=validated_data["shipping_address_id"])
        order = Order.objects.create(
            user=user,
            order_number=Order.generate_order_number(),
            subtotal=subtotal,
            discount=discount,
            shipping_fee=shipping_fee,
            tax=tax,
            grand_total=grand_total,
            payment_method=validated_data["payment_method"],
            payment_status="pending",
            order_status="pending",
            shipping_address=address,
            coupon=coupon,
            notes=validated_data.get("notes", ""),
        )

        for item in items:
            product = item.product
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                sku=product.sku,
                quantity=item.quantity,
                price=item.price,
                cost_price=product.cost_price,
                total=item.price * item.quantity,
            )
            product.stock_quantity -= item.quantity
            product.save(update_fields=["stock_quantity"])
            InventoryLog.objects.create(
                product=product,
                type="stock_out",
                quantity=item.quantity,
                reference=order.order_number,
                remarks=f"Order {order.order_number}",
                created_by=user,
            )
            if product.stock_quantity <= product.minimum_stock:
                Notification.objects.create(
                    user=None,
                    title="Low stock alert",
                    message=f"{product.name} ({product.sku}) is down to {product.stock_quantity} units.",
                    type="stock",
                    link=f"/admin/products/{product.pk}",
                )

        Payment.objects.create(
            order=order,
            transaction_id=f"TXN-{order.order_number}",
            payment_gateway=validated_data["payment_method"],
            amount=grand_total,
            currency="USD",
            status="pending",
        )
        if coupon and discount > 0:
            CouponUsage.objects.create(
                coupon=coupon, user=user, order=order, discount_amount=discount
            )
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

        OrderStatusHistory.objects.create(
            order=order, status="pending", note="Order placed", created_by=user
        )
        cart.items.all().delete()
        Notification.objects.create(
            user=user,
            title=f"Order {order.order_number} received",
            message="We have received your order and will process it shortly.",
            type="order",
            link=f"/orders/{order.pk}",
        )
        Notification.objects.create(
            user=None,
            title="New order received",
            message=f"{order.order_number} from {user.full_name} — ${grand_total}",
            type="order",
            link=f"/admin/orders/{order.pk}",
        )
        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    shipping_address_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Order
        fields = [
            "payment_method", "payment_status", "order_status", "shipping_address_id",
            "notes", "tracking_number",
        ]

    def validate(self, attrs):
        status = attrs.get("order_status", self.instance.order_status)
        tracking = attrs.get("tracking_number", self.instance.tracking_number)
        if status in ("shipped", "delivered") and not tracking:
            raise serializers.ValidationError(
                {"tracking_number": "A tracking number is required for shipped orders."}
            )
        return attrs
