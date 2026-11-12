from rest_framework import serializers

from apps.products.models import Product

from .models import InventoryLog


class StockLevelSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, default=None)
    image = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()
    stock_value = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "category_name", "brand_name", "image", "price",
            "cost_price", "stock_quantity", "minimum_stock", "stock_status",
            "stock_value", "status", "updated_at",
        ]

    def get_image(self, obj):
        image = obj.primary_image
        if image and image.image:
            request = self.context.get("request")
            return request.build_absolute_uri(image.image.url) if request else image.image.url
        return None

    def get_stock_status(self, obj):
        if obj.stock_quantity <= 0:
            return "out_of_stock"
        if obj.stock_quantity <= obj.minimum_stock:
            return "low_stock"
        return "in_stock"

    def get_stock_value(self, obj):
        return float(obj.stock_quantity * obj.cost_price)


class InventoryLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    type_display = serializers.CharField(source="get_type_display", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InventoryLog
        fields = [
            "id", "product", "product_name", "product_sku", "type", "type_display",
            "quantity", "reference", "remarks", "created_by", "created_by_name",
            "scheduled_date", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else "System"


class InventoryAdjustSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    type = serializers.ChoiceField(choices=InventoryLog.Type.choices)
    quantity = serializers.IntegerField(min_value=0)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=120)
    remarks = serializers.CharField(required=False, allow_blank=True)
    scheduled_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        product = attrs["product"]
        quantity = attrs["quantity"]
        kind = attrs["type"]
        if kind == "stock_out" and quantity > product.stock_quantity:
            raise serializers.ValidationError(
                {"quantity": f"Cannot remove {quantity}; only {product.stock_quantity} in stock."}
            )
        if kind in ("stock_in", "stock_out", "return") and quantity < 1:
            raise serializers.ValidationError({"quantity": "Quantity must be at least 1."})
        return attrs
