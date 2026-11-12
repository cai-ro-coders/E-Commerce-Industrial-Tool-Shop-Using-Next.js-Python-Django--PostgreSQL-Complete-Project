from rest_framework import serializers

from .models import FileDocument, Setting


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ["id", "key", "group", "value", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_key(self, value):
        value = value.strip().lower().replace(" ", "_")
        qs = Setting.objects.filter(key=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A setting with this key already exists.")
        return value

    def validate_value(self, value):
        if value and len(value) > 20000:
            raise serializers.ValidationError("Value is too long.")
        return value


class PublicSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ["key", "group", "value"]


class FileDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    size_display = serializers.SerializerMethodField()

    class Meta:
        model = FileDocument
        fields = [
            "id", "name", "file", "url", "category", "description", "size",
            "size_display", "content_type", "uploaded_by", "uploaded_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "size", "content_type", "uploaded_by", "created_at"]

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() if obj.uploaded_by else "System"

    def get_url(self, obj):
        request = self.context.get("request")
        url = obj.file.url if obj.file else ""
        return request.build_absolute_uri(url) if request and url else url

    def get_size_display(self, obj):
        size = obj.size or 0
        if size >= 1024 * 1024:
            return f"{size / 1024 / 1024:.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.0f} KB"
        return f"{size} B"

    def create(self, validated_data):
        file = validated_data.get("file")
        if file:
            validated_data["size"] = file.size
            validated_data["content_type"] = getattr(file, "content_type", "") or ""
            if not validated_data.get("name"):
                validated_data["name"] = file.name
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["uploaded_by"] = request.user
        return super().create(validated_data)
