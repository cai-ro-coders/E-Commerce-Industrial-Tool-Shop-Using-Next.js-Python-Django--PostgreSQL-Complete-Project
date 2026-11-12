from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        ORDER = "order", "Order"
        STOCK = "stock", "Stock"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="notifications", null=True, blank=True,
        on_delete=models.CASCADE, help_text="Blank = broadcast to all staff/admins",
    )
    title = models.CharField(max_length=180)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.INFO)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
