from django.contrib import admin

from apps.brands.models import Brand
from apps.cart.models import Cart, CartItem, Wishlist
from apps.categories.models import Category
from apps.core.models import FileDocument, Setting
from apps.coupons.models import Coupon, CouponUsage
from apps.inventory.models import InventoryLog
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem, OrderStatusHistory
from apps.payments.models import Payment
from apps.products.models import Product, ProductImage, ProductSpecification
from apps.reviews.models import Review


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductSpecInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "brand", "price", "stock_quantity", "status", "featured")
    list_filter = ("status", "featured", "category", "brand")
    search_fields = ("name", "sku", "short_description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductSpecInline]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("total",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "grand_total", "payment_status", "order_status", "created_at")
    list_filter = ("order_status", "payment_status", "payment_method")
    search_fields = ("order_number", "user__email", "tracking_number")
    inlines = [OrderItemInline, PaymentInline]


admin.site.register(Coupon)
admin.site.register(CouponUsage)
admin.site.register(Review)
admin.site.register(InventoryLog)
admin.site.register(Notification)
admin.site.register(Setting)
admin.site.register(FileDocument)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Wishlist)
admin.site.register(OrderStatusHistory)
