from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from apps.categories.models import Category
from apps.core.validators import validate_image_upload


class Product(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DRAFT = "draft", "Draft"
        INACTIVE = "inactive", "Inactive"

    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.PROTECT
    )
    brand = models.ForeignKey(
        "brands.Brand", related_name="products", null=True, blank=True, on_delete=models.SET_NULL
    )
    sku = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True, blank=True)
    short_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    weight = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Weight in kg")
    dimensions = models.CharField(max_length=100, blank=True, help_text="L x W x H in cm")
    stock_quantity = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=5)
    featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "featured"]),
            models.Index(fields=["stock_quantity"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:230]
            slug = base
            i = 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        return self.sale_price if self.sale_price and self.sale_price > 0 else self.price

    @property
    def discount_percent(self):
        if self.sale_price and self.price and self.sale_price < self.price:
            return round(float((self.price - self.sale_price) / self.price) * 100)
        return 0

    @property
    def profit_margin(self):
        price = self.effective_price or Decimal("0")
        if not price:
            return 0
        return round(float((price - self.cost_price) / price) * 100, 1)

    @property
    def in_stock(self):
        return self.stock_quantity > 0

    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity <= self.minimum_stock

    @property
    def is_out_of_stock(self):
        return self.stock_quantity <= 0

    @property
    def primary_image(self):
        image = self.images.filter(is_primary=True).first() or self.images.first()
        return image

    def get_primary_image_url(self):
        image = self.primary_image
        return image.image.url if image and image.image else None


class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="products/", validators=[validate_image_upload])
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "id"]

    def __str__(self):
        return f"{self.product.name} image"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            ProductImage.objects.filter(product=self.product).exclude(pk=self.pk).update(
                is_primary=False
            )


class ProductSpecification(models.Model):
    product = models.ForeignKey(
        Product, related_name="specifications", on_delete=models.CASCADE
    )
    attribute_name = models.CharField(max_length=120)
    attribute_value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.attribute_name}: {self.attribute_value}"
