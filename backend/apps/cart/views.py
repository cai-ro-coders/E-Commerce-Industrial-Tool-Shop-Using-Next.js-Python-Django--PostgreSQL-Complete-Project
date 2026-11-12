from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart.models import Cart, CartItem, Wishlist
from apps.core.mixins import EnvelopeListMixin
from apps.cart.serializers import (
    CartItemSerializer,
    CartSerializer,
    WishlistSerializer,
)
from apps.products.models import Product


def get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = get_cart(request.user)
        return Response(
            {
                "success": True,
                "data": CartSerializer(cart, context={"request": request}).data,
            }
        )

    def delete(self, request):
        cart = get_cart(request.user)
        cart.items.all().delete()
        return Response({"success": True, "message": "Cart cleared."})


class CartItemViewSet(EnvelopeListMixin, viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "put", "delete", "head", "options"]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user).select_related(
            "product", "product__category"
        ).prefetch_related("product__images")

    def create(self, request, *args, **kwargs):
        product_id = request.data.get("product") or request.data.get("product_id")
        quantity = int(request.data.get("quantity", 1))
        if not product_id:
            raise ValidationError({"product": "Product is required."})
        try:
            product = Product.objects.get(pk=product_id, status="active")
        except Product.DoesNotExist:
            return Response({"success": False, "message": "Product not found."}, status=404)
        if product.stock_quantity < quantity:
            return Response(
                {"success": False, "message": f"Only {product.stock_quantity} units available."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cart = get_cart(request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity, "price": product.effective_price},
        )
        if not created:
            item.quantity += quantity
            item.price = product.effective_price
            item.save(update_fields=["quantity", "price"])
        return Response(
            {
                "success": True,
                "message": f"{product.name} added to cart.",
                "data": CartItemSerializer(item, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        item = self.get_object()
        quantity = int(request.data.get("quantity", item.quantity))
        if quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})
        if quantity > item.product.stock_quantity:
            raise ValidationError({"quantity": f"Only {item.product.stock_quantity} units available."})
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return Response(
            {
                "success": True,
                "message": "Cart updated.",
                "data": CartItemSerializer(item, context={"request": request}).data,
            }
        )

    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        item.delete()
        return Response({"success": True, "message": "Item removed from cart."})

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        get_cart(request.user).items.all().delete()
        return Response({"success": True, "message": "Cart cleared."})


class WishlistViewSet(EnvelopeListMixin, viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related(
            "product"
        ).prefetch_related("product__images")

    def create(self, request, *args, **kwargs):
        product_id = request.data.get("product") or request.data.get("product_id")
        try:
            product = Product.objects.get(pk=product_id, status="active")
        except (Product.DoesNotExist, ValueError, TypeError):
            return Response({"success": False, "message": "Product not found."}, status=404)
        item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        return Response(
            {
                "success": True,
                "message": "Added to wishlist." if created else "Already in wishlist.",
                "data": WishlistSerializer(item, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"success": True, "message": "Removed from wishlist."})
