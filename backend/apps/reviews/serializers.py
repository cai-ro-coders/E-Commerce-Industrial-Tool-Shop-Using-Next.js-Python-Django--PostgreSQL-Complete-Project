from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_image = serializers.SerializerMethodField()
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "product", "product_name", "product_slug", "product_image",
            "user", "user_name", "user_email", "rating", "title", "comment",
            "status", "status_display", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]

    def get_product_image(self, obj):
        image = obj.product.primary_image
        if image and image.image:
            request = self.context.get("request")
            return request.build_absolute_uri(image.image.url) if request else image.image.url
        return None

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        product = attrs.get("product", getattr(self.instance, "product", None))
        if not self.instance and user:
            if Review.objects.filter(product=product, user=user).exists():
                raise serializers.ValidationError("You have already reviewed this product.")
        if not self.instance and user and user.role == "customer":
            attrs["status"] = "pending"
        return attrs
