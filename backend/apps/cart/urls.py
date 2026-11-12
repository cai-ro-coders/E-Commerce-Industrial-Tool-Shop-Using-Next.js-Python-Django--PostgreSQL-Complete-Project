from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CartItemViewSet, CartView, WishlistViewSet

router = DefaultRouter()
router.register("cart/items", CartItemViewSet, basename="cart-items")
router.register("wishlist", WishlistViewSet, basename="wishlist")

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("", include(router.urls)),
]
