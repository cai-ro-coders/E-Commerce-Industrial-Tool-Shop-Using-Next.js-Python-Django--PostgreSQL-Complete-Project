from django.conf import settings
from django.db import models


class InventoryLog(models.Model):
    class Type(models.TextChoices):
        STOCK_IN = "stock_in", "Stock In"
        STOCK_OUT = "stock_out", "Stock Out"
        ADJUSTMENT = "adjustment", "Adjustment"
        RETURN = "return", "Return"

    product = models.ForeignKey(
        "products.Product", related_name="inventory_logs", on_delete=models.CASCADE
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    quantity = models.IntegerField(help_text="Positive for in/return, positive count for out; absolute for adjustment")
    reference = models.CharField(max_length=120, blank=True)
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    scheduled_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.sku} {self.type} {self.quantity}"
