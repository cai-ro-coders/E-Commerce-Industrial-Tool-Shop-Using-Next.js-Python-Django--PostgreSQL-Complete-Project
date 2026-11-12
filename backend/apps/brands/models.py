from django.db import models
from django.utils.text import slugify

from apps.core.validators import validate_image_upload


class Brand(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    logo = models.ImageField(
        upload_to="brands/", null=True, blank=True, validators=[validate_image_upload]
    )
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:170]
            slug = base
            i = 2
            while Brand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)
