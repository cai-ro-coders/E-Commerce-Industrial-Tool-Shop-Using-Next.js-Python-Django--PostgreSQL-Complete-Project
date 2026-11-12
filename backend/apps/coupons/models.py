from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    class Type(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    code = models.CharField(max_length=50, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.PERCENTAGE)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    minimum_order = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    used_count = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.status == "active"
            and self.start_date <= now <= self.end_date
            and (self.usage_limit == 0 or self.used_count < self.usage_limit)
        )

    def calculate_discount(self, subtotal):
        subtotal = Decimal(str(subtotal))
        if not self.is_valid or subtotal < self.minimum_order:
            return Decimal("0")
        if self.type == "percentage":
            discount = subtotal * (Decimal(str(self.value)) / Decimal("100"))
        else:
            discount = Decimal(str(self.value))
        if self.maximum_discount:
            discount = min(discount, Decimal(str(self.maximum_discount)))
        return min(discount, subtotal).quantize(Decimal("0.01"))


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, related_name="usages", on_delete=models.CASCADE)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="coupon_usages", on_delete=models.CASCADE
    )
    order = models.ForeignKey(
        "orders.Order", related_name="coupon_usages", on_delete=models.CASCADE
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.coupon.code} - {self.user.email}"
