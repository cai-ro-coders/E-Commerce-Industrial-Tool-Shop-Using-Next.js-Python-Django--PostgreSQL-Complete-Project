from rest_framework import serializers

from apps.products.models import Product

from .models import Cart, CartItem, Wishlist


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()
    stock_quantity = serializers.IntegerField(source="product.stock_quantity", read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id", "product", "product_name", "product_sku", "product_slug",
            "product_image", "stock_quantity", "quantity", "price", "total",
            "created_at",
        ]
        read_only_fields = ["id", "price", "created_at"]

    def get_product_image(self, obj):
        image = obj.product.primary_image
        if not image or not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        if value > 999:
            raise serializers.ValidationError("Quantity is too large.")
        return value

    def create(self, validated_data):
        product = validated_data["product"]
        quantity = validated_data.get("quantity", 1)
        if product.stock_quantity < quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {product.stock_quantity} units are available."}
            )
        cart = validated_data["cart"]
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity, "price": product.effective_price},
        )
        if not created:
            new_qty = item.quantity + quantity
            if new_qty > product.stock_quantity:
                raise serializers.ValidationError(
                    {"quantity": f"Only {product.stock_quantity} units are available."}
                )
            item.quantity = new_qty
            item.price = product.effective_price
            item.save(update_fields=["quantity", "price"])
        return item


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    item_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "subtotal", "item_count", "created_at", "updated_at"]


class WishlistSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_price = serializers.DecimalField(source="product.effective_price", max_digits=12, decimal_places=2, read_only=True)
    product_image = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(source="product.in_stock", read_only=True)

    class Meta:
        model = Wishlist
        fields = [
            "id", "product", "product_name", "product_slug", "product_price",
            "product_image", "in_stock", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_product_image(self, obj):
        image = obj.product.primary_image
        if not image or not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url
