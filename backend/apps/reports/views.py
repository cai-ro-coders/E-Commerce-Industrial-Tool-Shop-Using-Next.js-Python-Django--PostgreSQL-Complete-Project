from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserListSerializer
from apps.core.permissions import IsAdminOrStaff
from apps.inventory.models import InventoryLog
from apps.orders.models import Order, OrderItem
from apps.orders.serializers import OrderListSerializer
from apps.products.models import Product
from apps.reviews.models import Review


def money(value):
    return round(float(value or 0), 2)


def image_url(product, request):
    image = product.primary_image if product else None
    if image and image.image:
        return request.build_absolute_uri(image.image.url) if request else image.image.url
    return None


def paid_orders():
    return Order.objects.filter(payment_status="paid")


def cost_expression():
    return ExpressionWrapper(
        F("items__cost_price") * F("items__quantity"), output_field=DecimalField()
    )


def revenue_series(months=12):
    now = timezone.now()
    start = (now - timedelta(days=31 * (months - 1))).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        paid_orders()
        .filter(created_at__gte=start)
        .annotate(period=TruncMonth("created_at"))
        .values("period")
        .annotate(revenue=Sum("grand_total"), orders=Count("id"))
        .order_by("period")
    )
    grouped = {row["period"].strftime("%Y-%m"): row for row in rows}
    series = []
    cursor = start
    for _ in range(months):
        key = cursor.strftime("%Y-%m")
        row = grouped.get(key)
        series.append(
            {
                "month": cursor.strftime("%b %Y"),
                "key": key,
                "revenue": money(row["revenue"]) if row else 0,
                "orders": row["orders"] if row else 0,
            }
        )
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return series


class DashboardView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        orders = Order.objects.all()
        paid = orders.filter(payment_status="paid")
        revenue = paid.aggregate(total=Sum("grand_total"))["total"] or 0
        cost = paid.aggregate(total=Sum(cost_expression()))["total"] or 0
        customers = User.objects.filter(role="customer")

        low_stock_qs = Product.objects.filter(
            stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock")
        ).select_related("category")

        best = (
            OrderItem.objects.filter(order__payment_status="paid")
            .values("product_id", "product_name")
            .annotate(qty=Sum("quantity"), revenue=Sum("total"))
            .order_by("-qty")[:5]
        )
        best_products = []
        for row in best:
            product = Product.objects.filter(pk=row["product_id"]).prefetch_related("images").first() if row["product_id"] else None
            best_products.append(
                {
                    "id": row["product_id"],
                    "name": row["product_name"],
                    "quantity_sold": row["qty"],
                    "revenue": money(row["revenue"]),
                    "image": image_url(product, request),
                }
            )

        week_start = today - timedelta(days=6)
        daily = (
            paid.filter(created_at__date__gte=week_start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(revenue=Sum("grand_total"), orders=Count("id"))
            .order_by("day")
        )
        daily_map = {row["day"]: row for row in daily}
        sales_analytic = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            row = daily_map.get(day)
            sales_analytic.append(
                {
                    "date": day.strftime("%a %d"),
                    "revenue": money(row["revenue"]) if row else 0,
                    "orders": row["orders"] if row else 0,
                }
            )

        recent_orders = Order.objects.select_related("user").prefetch_related("items__product__images")[:8]
        recent_customers = customers.order_by("-date_joined")[:5]

        return Response(
            {
                "success": True,
                "data": {
                    "stats": {
                        "total_revenue": money(revenue),
                        "net_earning": money(Decimal(revenue) - Decimal(cost)),
                        "today_orders": orders.filter(created_at__date=today).count(),
                        "yesterday_orders": orders.filter(created_at__date=yesterday).count(),
                        "total_orders": orders.count(),
                        "total_products": Product.objects.count(),
                        "total_customers": customers.count(),
                        "low_stock_products": low_stock_qs.count(),
                        "open_orders": orders.filter(order_status__in=["pending", "processing"]).count(),
                        "paid_orders": paid.count(),
                        "average_order_value": money(Decimal(revenue) / paid.count()) if paid.count() else 0,
                        "inventory_units": Product.objects.aggregate(total=Sum("stock_quantity"))["total"] or 0,
                        "pending_reviews": Review.objects.filter(status="pending").count(),
                    },
                    "revenue_analytics": revenue_series(12),
                    "sales_analytic": sales_analytic,
                    "order_status_distribution": [
                        {"status": row["order_status"], "count": row["count"]}
                        for row in orders.values("order_status").annotate(count=Count("id"))
                    ],
                    "payment_distribution": [
                        {"method": row["payment_method"], "count": row["count"]}
                        for row in orders.values("payment_method").annotate(count=Count("id"))
                    ],
                    "best_selling_products": best_products,
                    "recent_orders": OrderListSerializer(recent_orders, many=True, context={"request": request}).data,
                    "recent_customers": UserListSerializer(recent_customers, many=True).data,
                    "low_stock_list": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "sku": p.sku,
                            "stock_quantity": p.stock_quantity,
                            "minimum_stock": p.minimum_stock,
                            "image": image_url(p, request),
                        }
                        for p in low_stock_qs[:5]
                    ],
                },
            }
        )


class SalesReportView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        qs = Order.objects.all()
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        paid = qs.filter(payment_status="paid")
        revenue = paid.aggregate(total=Sum("grand_total"))["total"] or 0
        cost = paid.aggregate(total=Sum(cost_expression()))["total"] or 0

        group_by = request.query_params.get("group_by", "day")
        trunc = TruncMonth("created_at") if group_by == "month" else TruncDate("created_at")
        series_rows = (
            paid.annotate(period=trunc)
            .values("period")
            .annotate(revenue=Sum("grand_total"), orders=Count("id"), tax=Sum("tax"), shipping=Sum("shipping_fee"))
            .order_by("period")
        )
        series = [
            {
                "period": row["period"].strftime("%Y-%m-%d") if group_by == "day" else row["period"].strftime("%Y-%m"),
                "label": row["period"].strftime("%b %d") if group_by == "day" else row["period"].strftime("%b %Y"),
                "revenue": money(row["revenue"]),
                "orders": row["orders"],
                "tax": money(row["tax"]),
                "shipping": money(row["shipping"]),
            }
            for row in series_rows
        ]

        top_products = (
            OrderItem.objects.filter(order__in=paid)
            .values("product_id", "product_name", "sku")
            .annotate(quantity=Sum("quantity"), revenue=Sum("total"))
            .order_by("-revenue")[:10]
        )

        return Response(
            {
                "success": True,
                "data": {
                    "summary": {
                        "revenue": money(revenue),
                        "orders": qs.count(),
                        "paid_orders": paid.count(),
                        "net_earning": money(Decimal(revenue) - Decimal(cost)),
                        "tax_collected": money(paid.aggregate(total=Sum("tax"))["total"] or 0),
                        "shipping_collected": money(paid.aggregate(total=Sum("shipping_fee"))["total"] or 0),
                        "average_order_value": money(Decimal(revenue) / paid.count()) if paid.count() else 0,
                    },
                    "series": series,
                    "top_products": [
                        {**row, "revenue": money(row["revenue"])} for row in top_products
                    ],
                    "by_status": list(qs.values("order_status").annotate(count=Count("id"))),
                    "by_payment_method": list(qs.values("payment_method").annotate(count=Count("id"), revenue=Sum("grand_total"))),
                },
            }
        )


class ProductReportView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        category_rows = (
            Product.objects.values("category__name")
            .annotate(
                products=Count("id"),
                units=Sum("stock_quantity"),
                value=Sum(ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField())),
            )
            .order_by("-value")
        )
        sales = (
            OrderItem.objects.filter(order__payment_status="paid")
            .values("product_id", "product_name", "sku")
            .annotate(quantity=Sum("quantity"), revenue=Sum("total"))
            .order_by("-quantity")[:10]
        )
        low_stock = Product.objects.filter(stock_quantity__lte=F("minimum_stock")).values(
            "id", "name", "sku", "stock_quantity", "minimum_stock"
        )[:20]
        return Response(
            {
                "success": True,
                "data": {
                    "by_category": [
                        {
                            "category": row["category__name"],
                            "products": row["products"],
                            "units": row["units"],
                            "value": money(row["value"]),
                        }
                        for row in category_rows
                    ],
                    "best_sellers": [{**row, "revenue": money(row["revenue"])} for row in sales],
                    "low_stock": list(low_stock),
                    "totals": {
                        "products": Product.objects.count(),
                        "units": Product.objects.aggregate(total=Sum("stock_quantity"))["total"] or 0,
                        "out_of_stock": Product.objects.filter(stock_quantity__lte=0).count(),
                        "low_stock": Product.objects.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock")).count(),
                    },
                },
            }
        )


class InventoryReportView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        products = Product.objects.all()
        valuation = products.aggregate(
            cost=Sum(ExpressionWrapper(F("stock_quantity") * F("cost_price"), output_field=DecimalField())),
            retail=Sum(ExpressionWrapper(F("stock_quantity") * F("price"), output_field=DecimalField())),
            units=Sum("stock_quantity"),
        )
        movement_rows = (
            InventoryLog.objects.values("type")
            .annotate(count=Count("id"), quantity=Sum("quantity"))
            .order_by("type")
        )
        recent = (
            InventoryLog.objects.select_related("product", "created_by")
            .values("id", "product__name", "product__sku", "type", "quantity", "reference", "created_at")[:20]
        )
        return Response(
            {
                "success": True,
                "data": {
                    "summary": {
                        "products": products.count(),
                        "units": valuation["units"] or 0,
                        "cost_value": money(valuation["cost"]),
                        "retail_value": money(valuation["retail"]),
                        "potential_profit": money(Decimal(valuation["retail"] or 0) - Decimal(valuation["cost"] or 0)),
                        "low_stock": products.filter(stock_quantity__gt=0, stock_quantity__lte=F("minimum_stock")).count(),
                        "out_of_stock": products.filter(stock_quantity__lte=0).count(),
                    },
                    "movements": [
                        {"type": row["type"], "count": row["count"], "quantity": row["quantity"]}
                        for row in movement_rows
                    ],
                    "recent_movements": list(recent),
                },
            }
        )
