from django.conf import settings
from django.db import models

from apps.core.validators import validate_document_upload


class Setting(models.Model):
    GROUP_CHOICES = (
        ("general", "General"),
        ("company", "Company"),
        ("smtp", "SMTP"),
        ("payment", "Payment"),
        ("localization", "Localization"),
        ("appearance", "Appearance"),
        ("backup", "Backup"),
    )
    key = models.CharField(max_length=120, unique=True)
    group = models.CharField(max_length=40, choices=GROUP_CHOICES, default="general")
    value = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["group", "key"]

    def __str__(self):
        return f"{self.group}.{self.key}"


class FileDocument(models.Model):
    CATEGORY_CHOICES = (
        ("image", "Image"),
        ("document", "Document"),
        ("contract", "Contract"),
        ("invoice", "Invoice"),
        ("customer", "Customer File"),
        ("other", "Other"),
    )
    name = models.CharField(max_length=180)
    file = models.FileField(upload_to="files/%Y/%m/", validators=[validate_document_upload])
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="document")
    description = models.TextField(blank=True)
    size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
