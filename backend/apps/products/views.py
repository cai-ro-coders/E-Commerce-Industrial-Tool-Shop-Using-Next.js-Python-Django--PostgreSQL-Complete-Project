import csv
import re

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrStaffOrReadOnly
from apps.core.utils import log_activity

from .models import Product, ProductImage
from .serializers import (
    ProductImageSerializer,
    ProductListSerializer,
    ProductSerializer,
)


def product_queryset():
    value = ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField())
    return Product.objects.select_related("category", "brand").prefetch_related(
        "images", "specifications"
    ).annotate(
        rating_average=Avg("reviews__rating", filter=Q(reviews__status="approved")),
        review_count=Count("reviews", filter=Q(reviews__status="approved"), distinct=True),
        stock_value=value,
    )


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrStaffOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filterset_fields = ["category", "brand", "status", "featured"]
    search_fields = ["name", "sku", "short_description", "description"]
    ordering_fields = [
        "name", "price", "sale_price", "stock_quantity", "created_at",
        "rating_average", "review_count",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        qs = product_queryset()
        user = self.request.user
        is_staff = user.is_authenticated and user.role in ("admin", "staff")
        if not is_staff:
            qs = qs.filter(status="active")

        params = self.request.query_params
        if params.get("in_stock") == "true":
            qs = qs.filter(stock_quantity__gt=0)
        if params.get("low_stock") == "true":
            qs = qs.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock"))
        if params.get("out_of_stock") == "true":
            qs = qs.filter(stock_quantity__lte=0)
        if params.get("featured") == "true":
            qs = qs.filter(featured=True)
        if params.get("min_price"):
            qs = qs.filter(price__gte=params["min_price"])
        if params.get("max_price"):
            qs = qs.filter(price__lte=params["max_price"])
        if params.get("category_slug"):
            qs = qs.filter(category__slug=params["category_slug"])
        if params.get("brand_slug"):
            qs = qs.filter(brand__slug=params["brand_slug"])
        if params.get("slug"):
            qs = qs.filter(slug=params["slug"])
        return qs

    def perform_create(self, serializer):
        product = serializer.save()
        log_activity(self.request.user, "product.created", f"Created product {product.name}", "product", product.pk, self.request)
        if product.stock_quantity:
            from apps.inventory.models import InventoryLog

            InventoryLog.objects.create(
                product=product,
                type="stock_in",
                quantity=product.stock_quantity,
                reference=f"INIT-{product.sku}",
                remarks="Initial stock on product creation",
                created_by=self.request.user if self.request.user.is_authenticated else None,
            )

    def perform_update(self, serializer):
        product = serializer.save()
        log_activity(self.request.user, "product.updated", f"Updated product {product.name}", "product", product.pk, self.request)

    def perform_destroy(self, instance):
        log_activity(self.request.user, "product.deleted", f"Deleted product {instance.name}", "product", instance.pk, self.request)
        for image in instance.images.all():
            image.image.delete(save=False)
        instance.delete()

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Product.objects.all()
        value = qs.aggregate(
            total=Sum(
                ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField())
            )
        )["total"] or 0
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "active": qs.filter(status="active").count(),
                    "draft": qs.filter(status="draft").count(),
                    "inactive": qs.filter(status="inactive").count(),
                    "out_of_stock": qs.filter(stock_quantity__lte=0).count(),
                    "low_stock": qs.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock")).count(),
                    "inventory_units": qs.aggregate(total=Sum("stock_quantity"))["total"] or 0,
                    "inventory_value": float(value),
                },
            }
        )

    @action(detail=True, methods=["patch"])
    def toggle_status(self, request, pk=None):
        product = self.get_object()
        product.status = "inactive" if product.status == "active" else "active"
        product.save(update_fields=["status"])
        log_activity(request.user, "product.status_changed", f"{product.name} -> {product.status}", "product", product.pk, request)
        return Response({"success": True, "message": f"Product {product.status}.", "data": {"status": product.status}})

    @action(detail=True, methods=["patch"])
    def toggle_featured(self, request, pk=None):
        product = self.get_object()
        product.featured = not product.featured
        product.save(update_fields=["featured"])
        return Response({"success": True, "message": "Featured status updated.", "data": {"featured": product.featured}})

    @action(detail=True, methods=["post"], url_path="images")
    def upload_images(self, request, pk=None):
        product = self.get_object()
        files = request.FILES.getlist("images") or request.FILES.getlist("image")
        if not files:
            raise ValidationError("No images were provided.")
        if len(files) > 8:
            raise ValidationError("You can upload a maximum of 8 images at once.")
        serialized = []
        for index, file in enumerate(files):
            serializer = ProductImageSerializer(data={"image": file, "sort_order": index}, context={"request": request})
            if not serializer.is_valid():
                raise ValidationError({"images": serializer.errors})
            is_primary = not product.images.exists() and index == 0
            image = serializer.save(product=product, is_primary=is_primary)
            serialized.append(ProductImageSerializer(image, context={"request": request}).data)
        log_activity(request.user, "product.images_uploaded", f"Uploaded {len(serialized)} image(s) to {product.name}", "product", product.pk, request)
        return Response(
            {"success": True, "message": f"{len(serialized)} image(s) uploaded.", "data": serialized},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>\d+)")
    def delete_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        try:
            image = product.images.get(pk=image_id)
        except ProductImage.DoesNotExist:
            return Response({"success": False, "message": "Image not found."}, status=404)
        was_primary = image.is_primary
        image.image.delete(save=False)
        image.delete()
        if was_primary:
            # Query the model directly: `product.images` is prefetched by
            # get_object(), so its cached queryset still contains the image
            # that was just deleted and would raise ProductImage.NotUpdated.
            replacement = (
                ProductImage.objects.filter(product_id=product.pk)
                .order_by("-is_primary", "sort_order", "id")
                .first()
            )
            if replacement:
                replacement.is_primary = True
                replacement.save(update_fields=["is_primary"])
        return Response({"success": True, "message": "Image deleted."})

    @action(detail=True, methods=["patch"], url_path=r"images/(?P<image_id>\d+)/primary")
    def set_primary_image(self, request, pk=None, image_id=None):
        product = self.get_object()
        try:
            image = product.images.get(pk=image_id)
        except ProductImage.DoesNotExist:
            return Response({"success": False, "message": "Image not found."}, status=404)
        product.images.update(is_primary=False)
        image.is_primary = True
        image.save(update_fields=["is_primary"])
        return Response({"success": True, "message": "Primary image updated."})

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        product = self.get_object()
        qs = product_queryset().filter(
            Q(category=product.category) | Q(brand=product.brand), status="active"
        ).exclude(pk=product.pk)[:8]
        return Response(
            {"success": True, "data": ProductListSerializer(qs, many=True, context={"request": request}).data}
        )

    @action(detail=False, methods=["get"])
    def export(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="products.csv"'
        writer = csv.writer(response)
        writer.writerow(["SKU", "Name", "Category", "Brand", "Price", "Sale Price", "Cost", "Stock", "Min Stock", "Status", "Featured"])
        for p in qs:
            writer.writerow([
                p.sku, p.name, p.category.name, p.brand.name if p.brand else "",
                p.price, p.sale_price or "", p.cost_price, p.stock_quantity,
                p.minimum_stock, p.status, p.featured,
            ])
        log_activity(request.user, "product.exported", "Exported products CSV", "product", "", request)
        return response
