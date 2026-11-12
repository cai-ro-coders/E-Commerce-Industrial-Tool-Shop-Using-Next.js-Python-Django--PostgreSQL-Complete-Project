from django.contrib import admin
from django.urls import path

from .views import (
    DashboardView,
    InventoryReportView,
    ProductReportView,
    SalesReportView,
)

urlpatterns = [
    path("reports/dashboard/", DashboardView.as_view(), name="report-dashboard"),
    path("reports/sales/", SalesReportView.as_view(), name="report-sales"),
    path("reports/products/", ProductReportView.as_view(), name="report-products"),
    path("reports/inventory/", InventoryReportView.as_view(), name="report-inventory"),
]
