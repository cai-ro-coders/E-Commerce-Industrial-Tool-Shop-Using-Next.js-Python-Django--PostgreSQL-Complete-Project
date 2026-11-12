import json

from rest_framework import serializers

from .models import Product, ProductImage, ProductSpecification


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False)

    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "url", "is_primary", "sort_order", "created_at"]
        read_only_fields = ["id", "product", "created_at"]
        extra_kwargs = {"image": {"required": False}}

    def get_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class ProductSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ["id", "attribute_name", "attribute_value"]


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, default=None)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    primary_image = serializers.SerializerMethodField()
    in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    rating_average = serializers.FloatField(read_only=True, default=0)
    review_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "slug", "category", "category_name", "brand",
            "brand_name", "price", "sale_price", "effective_price", "cost_price",
            "stock_quantity", "minimum_stock", "featured", "status", "primary_image",
            "in_stock", "is_low_stock", "is_out_of_stock", "discount_percent",
            "rating_average", "review_count", "created_at",
        ]

    def get_primary_image(self, obj):
        image = obj.primary_image
        if not image or not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True, default=None)
    images = ProductImageSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(many=True, required=False)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_margin = serializers.FloatField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    discount_percent = serializers.IntegerField(read_only=True)
    primary_image = serializers.SerializerMethodField()
    rating_average = serializers.FloatField(read_only=True, default=0)
    review_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Product
        fields = [
            "id", "category", "category_name", "brand", "brand_name", "sku", "name",
            "slug", "short_description", "description", "price", "sale_price",
            "cost_price", "effective_price", "profit_margin", "weight", "dimensions",
            "stock_quantity", "minimum_stock", "featured", "status", "images",
            "specifications", "primary_image", "in_stock", "is_low_stock",
            "is_out_of_stock", "discount_percent", "rating_average", "review_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_primary_image(self, obj):
        image = obj.primary_image
        if not image or not image.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url

    def validate_sku(self, value):
        value = value.strip().upper()
        qs = Product.objects.filter(sku__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A product with this SKU already exists.")
        return value

    def validate(self, attrs):
        price = attrs.get("price", getattr(self.instance, "price", None))
        sale = attrs.get("sale_price", getattr(self.instance, "sale_price", None))
        cost = attrs.get("cost_price", getattr(self.instance, "cost_price", 0))
        if price is not None and price <= 0:
            raise serializers.ValidationError({"price": "Price must be greater than zero."})
        if sale is not None and sale and price and sale >= price:
            raise serializers.ValidationError({"sale_price": "Sale price must be lower than the regular price."})
        if cost is not None and cost < 0:
            raise serializers.ValidationError({"cost_price": "Cost price cannot be negative."})
        stock = attrs.get("stock_quantity", getattr(self.instance, "stock_quantity", 0))
        if stock is not None and stock < 0:
            raise serializers.ValidationError({"stock_quantity": "Stock quantity cannot be negative."})

        specs = attrs.get("specifications")
        if isinstance(specs, str):
            try:
                attrs["specifications"] = json.loads(specs)
            except (json.JSONDecodeError, TypeError):
                raise serializers.ValidationError({"specifications": "Invalid specifications format."})
        return attrs

    def _save_specifications(self, product, specs):
        if specs is None:
            return
        product.specifications.all().delete()
        for spec in specs:
            name = str(spec.get("attribute_name", "")).strip()
            value = str(spec.get("attribute_value", "")).strip()
            if name and value:
                ProductSpecification.objects.create(
                    product=product, attribute_name=name[:120], attribute_value=value[:255]
                )

    def create(self, validated_data):
        specs = validated_data.pop("specifications", None)
        product = Product.objects.create(**validated_data)
        self._save_specifications(product, specs)
        return product

    def update(self, instance, validated_data):
        specs = validated_data.pop("specifications", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        self._save_specifications(instance, specs)
        return instance
