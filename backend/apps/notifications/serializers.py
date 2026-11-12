from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "title", "message", "type", "type_display", "link", "is_read", "created_at"]
        read_only_fields = ["id", "created_at"]
