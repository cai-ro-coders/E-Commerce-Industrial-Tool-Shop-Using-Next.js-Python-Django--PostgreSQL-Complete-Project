from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InventoryAdjustView, InventoryLogViewSet, InventoryViewSet

router = DefaultRouter()
router.register("inventory", InventoryViewSet, basename="inventory")

urlpatterns = [
    path("inventory/adjust/", InventoryAdjustView.as_view(), name="inventory-adjust"),
    path(
        "inventory/movements/",
        InventoryLogViewSet.as_view({"get": "list"}),
        name="inventory-movements",
    ),
    path(
        "inventory/movements/<int:pk>/",
        InventoryLogViewSet.as_view({"get": "retrieve"}),
        name="inventory-movement-detail",
    ),
    path("", include(router.urls)),
]
