import random
import string

from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        CARD = "card", "Credit / Debit Card"
        PAYPAL = "paypal", "PayPal"
        STRIPE = "stripe", "Stripe"
        BANK = "bank", "Bank Transfer"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE
    )
    order_number = models.CharField(max_length=40, unique=True, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.COD
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    order_status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    shipping_address = models.ForeignKey(
        "accounts.Address", null=True, blank=True, on_delete=models.SET_NULL
    )
    coupon = models.ForeignKey(
        "coupons.Coupon", null=True, blank=True, on_delete=models.SET_NULL
    )
    notes = models.TextField(blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_status", "payment_status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.order_number

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def first_item(self):
        return self.items.first()

    @property
    def customer_name(self):
        return self.user.full_name

    @staticmethod
    def generate_order_number():
        prefix = timezone.now().strftime("ORD-%Y%m%d")
        while True:
            candidate = f"{prefix}-{''.join(random.choices(string.digits, k=5))}"
            if not Order.objects.filter(order_number=candidate).exists():
                return candidate

    def recalculate(self):
        self.subtotal = sum((item.total for item in self.items.all()), 0)
        self.grand_total = (
            self.subtotal - self.discount + self.shipping_fee + self.tax
        )
        return self.grand_total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(
        "products.Product", null=True, blank=True, on_delete=models.SET_NULL
    )
    product_name = models.CharField(max_length=220)
    sku = models.CharField(max_length=80)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.total = self.price * self.quantity
        super().save(*args, **kwargs)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order, related_name="status_history", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "order status history"

    def __str__(self):
        return f"{self.order.order_number}: {self.status}"
