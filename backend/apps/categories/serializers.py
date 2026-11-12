from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id", "parent", "parent_name", "name", "slug", "image", "image_url",
            "description", "status", "product_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_parent_name(self, obj):
        return obj.parent.name if obj.parent else None

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return value

    def validate_parent(self, value):
        if self.instance and value and value.pk == self.instance.pk:
            raise serializers.ValidationError("A category cannot be its own parent.")
        return value


class CategoryTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image", "status", "product_count", "children"]

    def get_children(self, obj):
        return CategoryTreeSerializer(obj.children.all(), many=True, context=self.context).data
