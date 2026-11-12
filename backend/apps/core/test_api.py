"""End-to-end API tests for the industrial tool shop.

These cover authentication, role-based permissions, catalog/cart/order flows,
inventory, notifications, settings, reports and the standard response envelope.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Address, LoginHistory, PasswordResetToken, User
from apps.brands.models import Brand
from apps.cart.models import CartItem, Wishlist
from apps.categories.models import Category
from apps.core.models import Setting
from apps.coupons.models import Coupon
from apps.inventory.models import InventoryLog
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.products.models import Product
from apps.reviews.models import Review

API = "/api/v1"


class BaseAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="admin@test.local",
            password="AdminPass123!",
            first_name="Ada",
            last_name="Admin",
            role="admin",
            status="active",
        )
        cls.staff = User.objects.create_user(
            email="staff@test.local",
            password="StaffPass123!",
            first_name="Sam",
            last_name="Staff",
            role="staff",
            status="active",
        )
        cls.customer = User.objects.create_user(
            email="customer@test.local",
            password="CustomerPass123!",
            first_name="Casey",
            last_name="Customer",
            role="customer",
            status="active",
        )
        cls.other_customer = User.objects.create_user(
            email="other@test.local",
            password="CustomerPass123!",
            first_name="Other",
            last_name="Customer",
            role="customer",
            status="active",
        )
        cls.category = Category.objects.create(name="Power Tools", status="active")
        cls.brand = Brand.objects.create(name="DeWalt", status="active")
        cls.product = Product.objects.create(
            category=cls.category,
            brand=cls.brand,
            sku="SKU-100",
            name="Cordless Drill",
            price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            stock_quantity=10,
            minimum_stock=2,
            status="active",
        )
        cls.address = Address.objects.create(
            user=cls.customer,
            full_name="Casey Customer",
            phone="+1 555 0100",
            address_line_1="1 Test Street",
            city="Testville",
            province="CA",
            postal_code="90210",
            country="United States",
        )

    def setUp(self):
        # Avoid throttle state leaking between test methods.
        cache.clear()
        self.client.force_authenticate(user=None)

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def make_coupon(self, code="SAVE10", **overrides):
        now = timezone.now()
        data = {
            "code": code,
            "type": "percentage",
            "value": Decimal("10.00"),
            "minimum_order": Decimal("0.00"),
            "usage_limit": 0,
            "start_date": now - timedelta(days=1),
            "end_date": now + timedelta(days=30),
            "status": "active",
        }
        data.update(overrides)
        return Coupon.objects.create(**data)

    def add_to_cart(self, quantity=1, product=None):
        product = product or self.product
        return self.client.post(
            f"{API}/cart/items/",
            {"product": product.id, "quantity": quantity},
            format="json",
        )

    def place_order(self, **overrides):
        payload = {
            "shipping_address_id": self.address.id,
            "payment_method": "cod",
            "notes": "Test order",
        }
        payload.update(overrides)
        return self.client.post(f"{API}/orders/", payload, format="json")


class AuthenticationTests(BaseAPITestCase):
    def test_login_returns_jwt_and_user(self):
        response = self.client.post(
            f"{API}/auth/login/",
            {"email": self.admin.email, "password": "AdminPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["email"], self.admin.email)
        self.assertTrue(
            LoginHistory.objects.filter(email=self.admin.email, success=True).exists()
        )

    def test_login_rejects_bad_password_and_records_failure(self):
        response = self.client.post(
            f"{API}/auth/login/",
            {"email": self.admin.email, "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertTrue(
            LoginHistory.objects.filter(email=self.admin.email, success=False).exists()
        )

    def test_inactive_account_cannot_log_in(self):
        self.customer.status = "inactive"
        self.customer.save(update_fields=["status"])
        response = self.client.post(
            f"{API}/auth/login/",
            {"email": self.customer.email, "password": "CustomerPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_profile_requires_authentication(self):
        response = self.client.get(f"{API}/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_get_and_update(self):
        self.auth(self.customer)
        response = self.client.get(f"{API}/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], self.customer.email)

        response = self.client.patch(
            f"{API}/auth/profile/",
            {"first_name": "Updated", "phone": "+1 555 9999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.phone, "+1 555 9999")

    def test_register_creates_customer_with_hashed_password(self):
        response = self.client.post(
            f"{API}/auth/register/",
            {
                "first_name": "New",
                "last_name": "Buyer",
                "email": "new.buyer@test.local",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new.buyer@test.local")
        self.assertEqual(user.role, "customer")
        self.assertTrue(user.check_password("StrongPass123!"))
        self.assertTrue(user.password.startswith("bcrypt"))
        self.assertIn("access", response.data["data"])

    def test_register_rejects_duplicate_email(self):
        response = self.client.post(
            f"{API}/auth/register/",
            {
                "first_name": "Dup",
                "last_name": "Buyer",
                "email": self.customer.email,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_change_password_and_login_with_new_password(self):
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/auth/change-password/",
            {
                "current_password": "CustomerPass123!",
                "new_password": "BrandNewPass123!",
                "confirm_password": "BrandNewPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password("BrandNewPass123!"))

        self.client.force_authenticate(user=None)
        login = self.client.post(
            f"{API}/auth/login/",
            {"email": self.customer.email, "password": "BrandNewPass123!"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

    def test_change_password_rejects_wrong_current_password(self):
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/auth/change-password/",
            {
                "current_password": "not-the-password",
                "new_password": "BrandNewPass123!",
                "confirm_password": "BrandNewPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_token_returns_new_access_token(self):
        login = self.client.post(
            f"{API}/auth/login/",
            {"email": self.customer.email, "password": "CustomerPass123!"},
            format="json",
        )
        refresh = login.data["data"]["refresh"]
        response = self.client.post(
            f"{API}/auth/refresh/", {"refresh": refresh}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post(
            f"{API}/auth/login/",
            {"email": self.customer.email, "password": "CustomerPass123!"},
            format="json",
        )
        refresh = login.data["data"]["refresh"]
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/auth/logout/", {"refresh": refresh}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            f"{API}/auth/refresh/", {"refresh": refresh}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_history_lists_recent_events(self):
        self.client.post(
            f"{API}/auth/login/",
            {"email": self.customer.email, "password": "CustomerPass123!"},
            format="json",
        )
        self.auth(self.customer)
        response = self.client.get(f"{API}/auth/login-history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertGreaterEqual(len(response.data["data"]), 1)

    def test_forgot_and_reset_password_flow(self):
        response = self.client.post(
            f"{API}/auth/forgot-password/",
            {"email": self.customer.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        token = PasswordResetToken.objects.get(user=self.customer).token

        response = self.client.post(
            f"{API}/auth/reset-password/",
            {
                "token": token,
                "password": "ResetPass123!",
                "confirm_password": "ResetPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password("ResetPass123!"))


class PermissionTests(BaseAPITestCase):
    def test_customer_cannot_reach_admin_only_endpoints(self):
        self.auth(self.customer)
        paths = [
            f"{API}/users/",
            f"{API}/customers/",
            f"{API}/coupons/",
            f"{API}/inventory/",
            f"{API}/activity-logs/",
            f"{API}/reports/dashboard/",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_can_read_public_catalog(self):
        for path in [
            f"{API}/products/",
            f"{API}/categories/",
            f"{API}/brands/",
            f"{API}/reviews/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_read_private_endpoints(self):
        for path in [f"{API}/users/", f"{API}/notifications/", f"{API}/addresses/"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertIn(
                    response.status_code,
                    (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
                )

    def test_customer_cannot_create_catalog_items(self):
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/products/",
            {
                "category": self.category.id,
                "sku": "NOPE-1",
                "name": "Nope",
                "price": "10.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_access_another_customers_address(self):
        other_address = Address.objects.create(
            user=self.other_customer,
            full_name="Other Customer",
            phone="+1 555 0200",
            address_line_1="2 Other Street",
            city="Otherville",
            province="NY",
            postal_code="10001",
            country="United States",
        )
        self.auth(self.customer)
        response = self.client.get(f"{API}/addresses/{other_address.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_only_sees_own_addresses(self):
        self.auth(self.customer)
        response = self.client.get(f"{API}/addresses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_users = {row["user"] for row in response.data["data"]}
        self.assertEqual(returned_users, {self.customer.id})


class ResponseEnvelopeTests(BaseAPITestCase):
    def test_paginated_list_uses_envelope(self):
        response = self.client.get(f"{API}/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsInstance(response.data["data"], list)
        self.assertIn("meta", response.data)

    def test_notifications_list_is_wrapped(self):
        Notification.objects.create(user=self.admin, title="Hello", message="World")
        self.auth(self.admin)
        response = self.client.get(f"{API}/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsInstance(response.data["data"], list)

    def test_wishlist_list_is_wrapped(self):
        Wishlist.objects.create(user=self.customer, product=self.product)
        self.auth(self.customer)
        response = self.client.get(f"{API}/wishlist/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsInstance(response.data["data"], list)

    def test_address_list_and_create_are_wrapped(self):
        self.auth(self.customer)
        response = self.client.get(f"{API}/addresses/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data["data"], list)

        response = self.client.post(
            f"{API}/addresses/",
            {
                "full_name": "Second Address",
                "phone": "+1 555 0300",
                "address_line_1": "3 New Street",
                "city": "Newville",
                "province": "TX",
                "postal_code": "73301",
                "country": "United States",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("id", response.data["data"])

    def test_cart_item_list_is_wrapped(self):
        self.auth(self.customer)
        self.add_to_cart()
        response = self.client.get(f"{API}/cart/items/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIsInstance(response.data["data"], list)


class CatalogCrudTests(BaseAPITestCase):
    def test_admin_can_create_update_and_delete_category(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/categories/",
            {"name": "Hand Tools", "status": "active"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        category_id = response.data["id"]

        response = self.client.patch(
            f"{API}/categories/{category_id}/",
            {"description": "Manual tools"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(f"{API}/categories/{category_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(pk=category_id).exists())

    def test_admin_can_create_brand(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/brands/", {"name": "Makita", "status": "active"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Brand.objects.filter(name="Makita").exists())

    def test_admin_product_create_records_initial_stock(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/products/",
            {
                "category": self.category.id,
                "brand": self.brand.id,
                "sku": "SKU-NEW",
                "name": "Impact Driver",
                "price": "150.00",
                "cost_price": "90.00",
                "stock_quantity": 7,
                "minimum_stock": 2,
                "status": "active",
                "specifications": [
                    {"attribute_name": "Voltage", "attribute_value": "18V"}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(sku="SKU-NEW")
        self.assertEqual(product.specifications.count(), 1)
        log = InventoryLog.objects.get(product=product, type="stock_in")
        self.assertEqual(log.quantity, 7)

    def test_admin_can_update_and_delete_product(self):
        self.auth(self.admin)
        response = self.client.patch(
            f"{API}/products/{self.product.id}/",
            {"price": "120.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.price, Decimal("120.00"))

        response = self.client.delete(f"{API}/products/{self.product.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=self.product.id).exists())

    def test_product_list_hides_inactive_items_from_public(self):
        draft = Product.objects.create(
            category=self.category,
            sku="SKU-DRAFT",
            name="Draft Tool",
            price=Decimal("50.00"),
            status="draft",
        )
        response = self.client.get(f"{API}/products/")
        ids = {row["id"] for row in response.data["data"]}
        self.assertNotIn(draft.id, ids)
        self.assertIn(self.product.id, ids)

        self.auth(self.admin)
        response = self.client.get(f"{API}/products/")
        ids = {row["id"] for row in response.data["data"]}
        self.assertIn(draft.id, ids)

    def test_product_search_filter_and_ordering(self):
        Product.objects.create(
            category=self.category,
            sku="SKU-200",
            name="Angle Grinder",
            price=Decimal("80.00"),
            status="active",
        )
        response = self.client.get(f"{API}/products/?search=Grinder")
        names = [row["name"] for row in response.data["data"]]
        self.assertEqual(names, ["Angle Grinder"])

        response = self.client.get(
            f"{API}/products/?category={self.category.id}&ordering=-price"
        )
        prices = [Decimal(row["price"]) for row in response.data["data"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_product_stats_endpoint(self):
        self.auth(self.admin)
        response = self.client.get(f"{API}/products/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total", response.data["data"])


class CartAndWishlistTests(BaseAPITestCase):
    def test_add_update_and_remove_cart_item(self):
        self.auth(self.customer)
        response = self.add_to_cart(quantity=2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item_id = response.data["data"]["id"]

        response = self.client.get(f"{API}/cart/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["item_count"], 2)
        self.assertEqual(Decimal(response.data["data"]["subtotal"]), Decimal("200.00"))

        response = self.client.patch(
            f"{API}/cart/items/{item_id}/", {"quantity": 3}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(CartItem.objects.get(pk=item_id).quantity, 3)

        response = self.client.delete(f"{API}/cart/items/{item_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(CartItem.objects.filter(pk=item_id).exists())

    def test_cannot_add_more_than_available_stock(self):
        self.auth(self.customer)
        response = self.add_to_cart(quantity=99)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(CartItem.objects.exists())

    def test_wishlist_add_duplicate_and_remove(self):
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/wishlist/", {"product": self.product.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        item_id = response.data["data"]["id"]

        response = self.client.post(
            f"{API}/wishlist/", {"product": self.product.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(f"{API}/wishlist/{item_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Wishlist.objects.filter(pk=item_id).exists())


class OrderFlowTests(BaseAPITestCase):
    def test_customer_can_place_order_and_stock_is_reserved(self):
        self.auth(self.customer)
        self.add_to_cart(quantity=2)
        response = self.place_order()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order_id = response.data["data"]["id"]
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.order_status, "pending")
        self.assertEqual(order.payment_method, "cod")
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(Decimal(order.subtotal), Decimal("200.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertFalse(CartItem.objects.filter(cart__user=self.customer).exists())
        self.assertTrue(Notification.objects.filter(user=self.customer).exists())

    def test_order_requires_non_empty_cart(self):
        self.auth(self.customer)
        response = self.place_order()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_order_rejects_invalid_payment_method(self):
        self.auth(self.customer)
        self.add_to_cart()
        response = self.place_order(payment_method="bitcoin")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_with_coupon_applies_discount_and_usage(self):
        coupon = self.make_coupon(value=Decimal("10.00"))
        self.auth(self.customer)
        self.add_to_cart(quantity=1)
        response = self.place_order(coupon_code=coupon.code)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(pk=response.data["data"]["id"])
        self.assertEqual(order.discount, Decimal("10.00"))
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

    def test_admin_status_transitions_and_restock_on_cancel(self):
        self.auth(self.customer)
        self.add_to_cart(quantity=2)
        order_id = self.place_order().data["data"]["id"]
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 8)

        self.auth(self.admin)
        response = self.client.patch(
            f"{API}/orders/{order_id}/status/",
            {"order_status": "shipped"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.patch(
            f"{API}/orders/{order_id}/status/",
            {"order_status": "shipped", "tracking_number": "TRK-123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.order_status, "shipped")
        self.assertEqual(order.tracking_number, "TRK-123")
        self.assertIsNotNone(order.shipped_at)

        response = self.client.patch(
            f"{API}/orders/{order_id}/status/",
            {"order_status": "cancelled"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertTrue(
            InventoryLog.objects.filter(
                product=self.product, type="return", reference=order.order_number
            ).exists()
        )

    def test_admin_can_mark_order_paid_and_view_stats(self):
        self.auth(self.customer)
        self.add_to_cart(quantity=1)
        order_id = self.place_order().data["data"]["id"]

        self.auth(self.admin)
        response = self.client.patch(
            f"{API}/orders/{order_id}/payment/",
            {"payment_status": "paid"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Order.objects.get(pk=order_id).payment_status, "paid")

        response = self.client.get(f"{API}/orders/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("total_orders", "paid_orders", "total_revenue", "average_order_value"):
            self.assertIn(key, response.data["data"])

    def test_customer_cannot_update_order_status(self):
        self.auth(self.customer)
        self.add_to_cart()
        order_id = self.place_order().data["data"]["id"]
        response = self.client.patch(
            f"{API}/orders/{order_id}/status/",
            {"order_status": "shipped", "tracking_number": "X"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_retrieve_another_customers_order(self):
        self.auth(self.customer)
        self.add_to_cart()
        order_id = self.place_order().data["data"]["id"]

        self.auth(self.other_customer)
        response = self.client.get(f"{API}/orders/{order_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_export_orders_csv(self):
        self.auth(self.customer)
        self.add_to_cart()
        order = self.place_order().data["data"]

        self.auth(self.admin)
        response = self.client.get(f"{API}/orders/export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn(order["order_number"], response.content.decode())


class AccountSummaryTests(BaseAPITestCase):
    def test_account_summary_requires_authentication(self):
        response = self.client.get(f"{API}/auth/account-summary/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_account_summary_is_empty_for_new_customer(self):
        self.auth(self.customer)
        response = self.client.get(f"{API}/auth/account-summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["total_orders"], 0)
        self.assertEqual(data["pending_orders"], 0)
        self.assertEqual(data["wishlist_items"], 0)
        self.assertEqual(data["cart_items"], 0)
        self.assertEqual(Decimal(data["total_spent"]), Decimal("0"))
        self.assertEqual(data["unread_notifications"], 0)
        self.assertEqual(data["recent_orders"], [])

    def test_account_summary_aggregates_only_the_current_customers_data(self):
        Order.objects.create(
            user=self.customer,
            order_number="ORD-ACC-1",
            grand_total=Decimal("120.00"),
            payment_status="paid",
            order_status="pending",
        )
        Order.objects.create(
            user=self.customer,
            order_number="ORD-ACC-2",
            grand_total=Decimal("80.00"),
            payment_status="paid",
            order_status="processing",
        )
        Order.objects.create(
            user=self.customer,
            order_number="ORD-ACC-3",
            grand_total=Decimal("45.00"),
            payment_status="pending",
            order_status="pending",
        )
        Order.objects.create(
            user=self.other_customer,
            order_number="ORD-ACC-4",
            grand_total=Decimal("999.00"),
            payment_status="paid",
            order_status="pending",
        )
        Wishlist.objects.create(user=self.customer, product=self.product)
        Notification.objects.create(
            user=self.customer, title="Order shipped", message="Your order is on the way."
        )
        Notification.objects.create(
            user=self.customer,
            title="Welcome",
            message="Thanks for joining.",
            is_read=True,
        )
        Notification.objects.create(
            user=self.other_customer, title="Other user", message="Should not count."
        )

        self.auth(self.customer)
        self.add_to_cart(quantity=2)
        response = self.client.get(f"{API}/auth/account-summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["total_orders"], 3)
        self.assertEqual(data["pending_orders"], 3)
        self.assertEqual(data["wishlist_items"], 1)
        self.assertEqual(data["cart_items"], 2)
        self.assertEqual(Decimal(data["total_spent"]), Decimal("200.00"))
        self.assertEqual(data["unread_notifications"], 1)
        self.assertEqual(len(data["recent_orders"]), 3)
        order_numbers = {order["order_number"] for order in data["recent_orders"]}
        self.assertEqual(order_numbers, {"ORD-ACC-1", "ORD-ACC-2", "ORD-ACC-3"})

    def test_account_summary_recent_orders_are_limited_to_five(self):
        for index in range(6):
            Order.objects.create(
                user=self.customer,
                order_number=f"ORD-LIMIT-{index}",
                grand_total=Decimal("10.00"),
                payment_status="pending",
                order_status="pending",
            )

        self.auth(self.customer)
        response = self.client.get(f"{API}/auth/account-summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["total_orders"], 6)
        self.assertEqual(len(response.data["data"]["recent_orders"]), 5)

    def test_profile_exposes_order_totals(self):
        Order.objects.create(
            user=self.customer,
            order_number="ORD-PROFILE-1",
            grand_total=Decimal("75.00"),
            payment_status="paid",
            order_status="pending",
        )
        Order.objects.create(
            user=self.customer,
            order_number="ORD-PROFILE-2",
            grand_total=Decimal("25.00"),
            payment_status="pending",
            order_status="pending",
        )

        self.auth(self.customer)
        response = self.client.get(f"{API}/auth/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["orders_count"], 2)
        self.assertEqual(Decimal(response.data["data"]["total_spent"]), Decimal("75.00"))


class StripePaymentTests(BaseAPITestCase):
    def configure_stripe(self, publishable="pk_test_123", secret="sk_test_123", webhook="whsec_123"):
        Setting.objects.update_or_create(
            key="stripe_publishable_key",
            defaults={"group": "payment", "value": publishable},
        )
        Setting.objects.update_or_create(
            key="stripe_secret_key",
            defaults={"group": "payment", "value": secret},
        )
        Setting.objects.update_or_create(
            key="stripe_webhook_secret",
            defaults={"group": "payment", "value": webhook},
        )

    def place_stripe_order(self):
        self.auth(self.customer)
        self.add_to_cart(quantity=1)
        response = self.place_order(payment_method="stripe")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Order.objects.get(pk=response.data["data"]["id"])

    def test_stripe_config_requires_auth_and_hides_secret(self):
        response = self.client.get(f"{API}/payments/stripe/config/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.configure_stripe()
        self.auth(self.customer)
        response = self.client.get(f"{API}/payments/stripe/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertTrue(data["enabled"])
        self.assertEqual(data["publishable_key"], "pk_test_123")
        self.assertEqual(data["mode"], "test")
        self.assertNotIn("sk_test_123", str(response.data))

    def test_create_intent_requires_stripe_settings(self):
        order = self.place_stripe_order()
        response = self.client.post(
            f"{API}/payments/stripe/create-intent/",
            {"order_id": order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_create_intent_returns_client_secret_and_updates_payment(self):
        self.configure_stripe()
        order = self.place_stripe_order()
        amount = int(order.grand_total * 100)
        intent = SimpleNamespace(
            id="pi_test_123",
            client_secret="pi_test_123_secret",
            amount=amount,
            currency="usd",
            status="requires_payment_method",
        )

        with patch(
            "apps.payments.views.stripe.PaymentIntent.create", return_value=intent
        ) as create:
            response = self.client.post(
                f"{API}/payments/stripe/create-intent/",
                {"order_id": order.id},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["client_secret"], "pi_test_123_secret")
        self.assertEqual(data["publishable_key"], "pk_test_123")
        self.assertEqual(data["order_id"], order.id)
        self.assertEqual(create.call_args.kwargs["amount"], amount)
        self.assertEqual(create.call_args.kwargs["currency"], "usd")
        payment = order.payments.first()
        payment.refresh_from_db()
        self.assertEqual(payment.transaction_id, "pi_test_123")
        self.assertEqual(payment.payment_gateway, "stripe")
        self.assertEqual(payment.status, "pending")

    def test_create_intent_reuses_succeeded_intent(self):
        self.configure_stripe()
        order = self.place_stripe_order()
        amount = int(order.grand_total * 100)
        payment = order.payments.first()
        payment.transaction_id = "pi_test_done"
        payment.payment_gateway = "stripe"
        payment.save()

        existing = SimpleNamespace(
            id="pi_test_done",
            client_secret="pi_test_done_secret",
            amount=amount,
            currency="usd",
            status="succeeded",
        )

        with patch(
            "apps.payments.views.stripe.PaymentIntent.retrieve", return_value=existing
        ), patch(
            "apps.payments.views.stripe.PaymentIntent.create"
        ) as create:
            response = self.client.post(
                f"{API}/payments/stripe/create-intent/",
                {"order_id": order.id},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "succeeded")
        self.assertEqual(response.data["data"]["payment_intent_id"], "pi_test_done")
        create.assert_not_called()

    def test_create_intent_rejects_another_customers_order(self):
        self.configure_stripe()
        order = Order.objects.create(
            user=self.other_customer,
            order_number="ORD-STRIPE-OTHER",
            grand_total=Decimal("50.00"),
            payment_method="stripe",
            payment_status="pending",
            order_status="pending",
        )
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/payments/stripe/create-intent/",
            {"order_id": order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_confirm_marks_order_and_payment_paid(self):
        self.configure_stripe()
        order = self.place_stripe_order()
        amount = int(order.grand_total * 100)
        intent = SimpleNamespace(
            id="pi_test_paid",
            metadata={"order_id": str(order.id)},
            status="succeeded",
            amount=amount,
            currency="usd",
        )

        with patch(
            "apps.payments.views.stripe.PaymentIntent.retrieve", return_value=intent
        ):
            response = self.client.post(
                f"{API}/payments/stripe/confirm/",
                {"payment_intent_id": "pi_test_paid"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        payment = order.payments.get(transaction_id="pi_test_paid")
        self.assertEqual(payment.status, "paid")
        self.assertIsNotNone(payment.paid_at)
        self.assertTrue(
            order.status_history.filter(note="Stripe payment received").exists()
        )

    def test_confirm_rejects_incomplete_intent(self):
        self.configure_stripe()
        order = self.place_stripe_order()
        intent = SimpleNamespace(
            id="pi_test_incomplete",
            metadata={"order_id": str(order.id)},
            status="requires_payment_method",
            amount=int(order.grand_total * 100),
            currency="usd",
        )

        with patch(
            "apps.payments.views.stripe.PaymentIntent.retrieve", return_value=intent
        ):
            response = self.client.post(
                f"{API}/payments/stripe/confirm/",
                {"payment_intent_id": "pi_test_incomplete"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_webhook_marks_order_paid(self):
        self.configure_stripe()
        order = self.place_stripe_order()
        intent = SimpleNamespace(
            id="pi_test_webhook",
            metadata={"order_id": str(order.id)},
            status="succeeded",
            amount=int(order.grand_total * 100),
            currency="usd",
        )
        event = {"type": "payment_intent.succeeded", "data": {"object": intent}}

        with patch(
            "apps.payments.views.stripe.Webhook.construct_event", return_value=event
        ):
            response = self.client.generic(
                "POST",
                f"{API}/payments/stripe/webhook/",
                "{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test-signature",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        self.assertTrue(order.payments.filter(transaction_id="pi_test_webhook", status="paid").exists())

    def test_webhook_requires_signing_secret(self):
        self.configure_stripe(webhook="")
        response = self.client.generic(
            "POST",
            f"{API}/payments/stripe/webhook/",
            "{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)


class PayPalPaymentTests(BaseAPITestCase):
    def configure_paypal(self, client_id="paypal-client-123", secret="paypal-secret-123", mode="sandbox"):
        Setting.objects.update_or_create(
            key="paypal_client_id",
            defaults={"group": "payment", "value": client_id},
        )
        Setting.objects.update_or_create(
            key="paypal_client_secret",
            defaults={"group": "payment", "value": secret},
        )
        Setting.objects.update_or_create(
            key="paypal_mode",
            defaults={"group": "payment", "value": mode},
        )

    def place_paypal_order(self):
        self.auth(self.customer)
        self.add_to_cart(quantity=1)
        response = self.place_order(payment_method="paypal")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Order.objects.get(pk=response.data["data"]["id"])

    def captured_order_payload(self, order, amount=None, currency="USD"):
        value = str(amount if amount is not None else order.grand_total)
        return {
            "id": "PAYPAL-ORDER-1",
            "status": "COMPLETED",
            "purchase_units": [
                {
                    "custom_id": str(order.pk),
                    "reference_id": order.order_number,
                    "amount": {"currency_code": currency, "value": value},
                    "payments": {
                        "captures": [
                            {"amount": {"currency_code": currency, "value": value}}
                        ]
                    },
                }
            ],
        }

    def test_paypal_config_requires_auth_and_hides_secret(self):
        response = self.client.get(f"{API}/payments/paypal/config/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.configure_paypal()
        self.auth(self.customer)
        response = self.client.get(f"{API}/payments/paypal/config/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertTrue(data["enabled"])
        self.assertEqual(data["client_id"], "paypal-client-123")
        self.assertEqual(data["mode"], "sandbox")
        self.assertEqual(data["currency"], "USD")
        self.assertNotIn("paypal-secret-123", str(response.data))

    def test_create_order_requires_paypal_settings(self):
        order = self.place_paypal_order()
        response = self.client.post(
            f"{API}/payments/paypal/create-order/",
            {"order_id": order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_create_order_returns_paypal_id_and_stores_payment(self):
        self.configure_paypal()
        order = self.place_paypal_order()

        with patch(
            "apps.payments.views._paypal_request",
            return_value=(200, {"id": "PAYPAL-ORDER-1", "status": "CREATED"}),
        ) as request_mock:
            response = self.client.post(
                f"{API}/payments/paypal/create-order/",
                {"order_id": order.id},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        self.assertEqual(data["paypal_order_id"], "PAYPAL-ORDER-1")
        self.assertEqual(data["client_id"], "paypal-client-123")
        self.assertEqual(data["currency"], "USD")
        self.assertNotIn("paypal-secret-123", str(response.data))

        payload = request_mock.call_args.args[3]
        self.assertEqual(payload["intent"], "CAPTURE")
        self.assertEqual(payload["purchase_units"][0]["custom_id"], str(order.pk))
        self.assertEqual(
            payload["purchase_units"][0]["amount"]["value"],
            f"{order.grand_total:.2f}",
        )

        payment = order.payments.get(transaction_id="PAYPAL-ORDER-1")
        self.assertEqual(payment.payment_gateway, "paypal")
        self.assertEqual(payment.status, "pending")

    def test_create_order_rejects_non_paypal_order(self):
        self.configure_paypal()
        self.auth(self.customer)
        self.add_to_cart(quantity=1)
        response = self.place_order(payment_method="cod")
        order = Order.objects.get(pk=response.data["data"]["id"])

        response = self.client.post(
            f"{API}/payments/paypal/create-order/",
            {"order_id": order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_order_rejects_another_customers_order(self):
        self.configure_paypal()
        order = Order.objects.create(
            user=self.other_customer,
            order_number="ORD-PAYPAL-OTHER",
            grand_total=Decimal("50.00"),
            payment_method="paypal",
            payment_status="pending",
            order_status="pending",
        )
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/payments/paypal/create-order/",
            {"order_id": order.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_capture_marks_order_and_payment_paid(self):
        self.configure_paypal()
        order = self.place_paypal_order()

        with patch(
            "apps.payments.views._paypal_request",
            return_value=(200, self.captured_order_payload(order)),
        ):
            response = self.client.post(
                f"{API}/payments/paypal/capture/",
                {"order_id": order.id, "paypal_order_id": "PAYPAL-ORDER-1"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "paid")
        payment = order.payments.get(transaction_id="PAYPAL-ORDER-1")
        self.assertEqual(payment.status, "paid")
        self.assertEqual(payment.payment_gateway, "paypal")
        self.assertEqual(payment.currency, "USD")
        self.assertIsNotNone(payment.paid_at)
        self.assertTrue(
            order.status_history.filter(note="PayPal payment received").exists()
        )

    def test_capture_rejects_amount_mismatch(self):
        self.configure_paypal()
        order = self.place_paypal_order()
        payload = self.captured_order_payload(order, amount="1.00")

        with patch(
            "apps.payments.views._paypal_request", return_value=(200, payload)
        ):
            response = self.client.post(
                f"{API}/payments/paypal/capture/",
                {"order_id": order.id, "paypal_order_id": "PAYPAL-ORDER-1"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_capture_rejects_currency_mismatch(self):
        self.configure_paypal()
        order = self.place_paypal_order()
        payload = self.captured_order_payload(order, currency="EUR")

        with patch(
            "apps.payments.views._paypal_request", return_value=(200, payload)
        ):
            response = self.client.post(
                f"{API}/payments/paypal/capture/",
                {"order_id": order.id, "paypal_order_id": "PAYPAL-ORDER-1"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, "pending")

    def test_capture_rejects_another_customers_order(self):
        self.configure_paypal()
        order = Order.objects.create(
            user=self.other_customer,
            order_number="ORD-PAYPAL-OTHER-2",
            grand_total=Decimal("50.00"),
            payment_method="paypal",
            payment_status="pending",
            order_status="pending",
        )
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/payments/paypal/capture/",
            {"order_id": order.id, "paypal_order_id": "PAYPAL-ORDER-1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CouponTests(BaseAPITestCase):
    def test_validate_coupon_is_public_and_returns_discount(self):
        coupon = self.make_coupon(value=Decimal("10.00"))
        response = self.client.post(
            f"{API}/coupons/validate/",
            {"code": coupon.code, "subtotal": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(response.data["data"]["discount"]), Decimal("10.00"))

    def test_validate_coupon_enforces_minimum_order(self):
        coupon = self.make_coupon(minimum_order=Decimal("500.00"))
        response = self.client.post(
            f"{API}/coupons/validate/",
            {"code": coupon.code, "subtotal": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_rejects_expired_coupon(self):
        now = timezone.now()
        coupon = self.make_coupon(
            code="OLD10",
            start_date=now - timedelta(days=30),
            end_date=now - timedelta(days=1),
        )
        response = self.client.post(
            f"{API}/coupons/validate/",
            {"code": coupon.code, "subtotal": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_coupon_crud_and_stats(self):
        self.auth(self.admin)
        now = timezone.now()
        response = self.client.post(
            f"{API}/coupons/",
            {
                "code": "new20",
                "type": "percentage",
                "value": "20.00",
                "minimum_order": "50.00",
                "usage_limit": 5,
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=10)).isoformat(),
                "status": "active",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        coupon_id = response.data["id"]
        self.assertEqual(Coupon.objects.get(pk=coupon_id).code, "NEW20")

        response = self.client.get(f"{API}/coupons/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total", response.data["data"])


class ReviewTests(BaseAPITestCase):
    def _create_review(self, rating=5):
        return self.client.post(
            f"{API}/reviews/",
            {
                "product": self.product.id,
                "rating": rating,
                "title": "Great tool",
                "comment": "Works well",
            },
            format="json",
        )

    def test_customer_review_starts_pending_and_hidden_from_public(self):
        self.auth(self.customer)
        response = self._create_review()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")

        self.client.force_authenticate(user=None)
        response = self.client.get(f"{API}/reviews/?product={self.product.id}")
        self.assertEqual(response.data["data"], [])

    def test_customer_cannot_review_same_product_twice(self):
        self.auth(self.customer)
        self._create_review()
        response = self._create_review(rating=4)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_moderates_review_and_public_can_see_it(self):
        self.auth(self.customer)
        review_id = self._create_review().data["id"]

        self.auth(self.admin)
        response = self.client.patch(
            f"{API}/reviews/{review_id}/moderate/",
            {"status": "approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["status"], "approved")

        self.client.force_authenticate(user=None)
        response = self.client.get(f"{API}/reviews/?product={self.product.id}")
        ids = [row["id"] for row in response.data["data"]]
        self.assertIn(review_id, ids)

    def test_customer_cannot_moderate_reviews(self):
        self.auth(self.customer)
        review_id = self._create_review().data["id"]
        response = self.client.patch(
            f"{API}/reviews/{review_id}/moderate/",
            {"status": "approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_review_stats(self):
        Review.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            title="Good",
            comment="Good",
            status="pending",
        )
        self.auth(self.admin)
        response = self.client.get(f"{API}/reviews/stats/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("pending", response.data["data"])


class InventoryTests(BaseAPITestCase):
    def test_stock_adjustments_update_product_and_log(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/inventory/adjust/",
            {
                "product": self.product.id,
                "type": "stock_in",
                "quantity": 5,
                "reference": "PO-1",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 15)

        response = self.client.post(
            f"{API}/inventory/adjust/",
            {"product": self.product.id, "type": "stock_out", "quantity": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 12)

        response = self.client.post(
            f"{API}/inventory/adjust/",
            {"product": self.product.id, "type": "adjustment", "quantity": 7},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

        self.assertEqual(
            InventoryLog.objects.filter(product=self.product).count(), 3
        )

    def test_stock_out_beyond_available_is_rejected(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/inventory/adjust/",
            {"product": self.product.id, "type": "stock_out", "quantity": 999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_low_stock_adjustment_creates_notification(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/inventory/adjust/",
            {"product": self.product.id, "type": "adjustment", "quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(type="stock", user__isnull=True).exists()
        )

    def test_inventory_dashboard_endpoints(self):
        self.auth(self.admin)
        for path in (
            f"{API}/inventory/",
            f"{API}/inventory/stats/",
            f"{API}/inventory/valuation/",
            f"{API}/inventory/low_stock/",
            f"{API}/inventory/movements/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_200_OK)


class NotificationTests(BaseAPITestCase):
    def test_admin_can_broadcast_and_manage_notifications(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/notifications/",
            {
                "title": "Maintenance",
                "message": "System maintenance tonight.",
                "type": "info",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification_id = response.data["data"]["id"]
        self.assertIsNone(Notification.objects.get(pk=notification_id).user)

        response = self.client.get(f"{API}/notifications/")
        self.assertIn(notification_id, [row["id"] for row in response.data["data"]])

        response = self.client.patch(f"{API}/notifications/{notification_id}/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Notification.objects.get(pk=notification_id).is_read)

        response = self.client.get(f"{API}/notifications/unread_count/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data["data"])

        Notification.objects.create(
            user=self.admin, title="Personal", message="Mine", is_read=False
        )
        response = self.client.post(f"{API}/notifications/read-all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Notification.objects.filter(is_read=False).exists())

        response = self.client.delete(f"{API}/notifications/{notification_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_customer_only_receives_own_notifications(self):
        Notification.objects.create(user=self.customer, title="Mine", message="Hello")
        Notification.objects.create(user=self.other_customer, title="Theirs", message="Hi")
        self.auth(self.customer)
        response = self.client.get(f"{API}/notifications/")
        titles = [row["title"] for row in response.data["data"]]
        self.assertEqual(titles, ["Mine"])

    def test_customer_cannot_broadcast(self):
        self.auth(self.customer)
        response = self.client.post(
            f"{API}/notifications/",
            {"title": "Spam", "message": "Nope", "type": "info"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class SettingsAndUserTests(BaseAPITestCase):
    def test_settings_public_excludes_sensitive_groups(self):
        Setting.objects.create(key="site_name", group="general", value="Tool Shop")
        Setting.objects.create(key="stripe_key", group="payment", value="sk_live")
        Setting.objects.create(key="email_host", group="smtp", value="smtp.local")
        Setting.objects.create(key="auto_backup", group="backup", value="true")

        response = self.client.get(f"{API}/settings/public/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        keys = {row["key"] for row in response.data["data"]}
        self.assertIn("site_name", keys)
        self.assertNotIn("stripe_key", keys)
        self.assertNotIn("email_host", keys)
        self.assertNotIn("auto_backup", keys)

    def test_admin_bulk_updates_settings(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/settings/bulk_update/",
            {
                "settings": [
                    {"key": "site_name", "value": "Updated Shop", "group": "general"},
                    {"key": "currency", "value": "USD", "group": "localization"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Setting.objects.get(key="site_name").value, "Updated Shop")

    def test_admin_can_create_and_toggle_users(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/users/",
            {
                "email": "new.staff@test.local",
                "first_name": "New",
                "last_name": "Staff",
                "role": "staff",
                "status": "active",
                "password": "NewStaffPass123!",
                "confirm_password": "NewStaffPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new.staff@test.local")
        self.assertTrue(user.check_password("NewStaffPass123!"))

        response = self.client.patch(f"{API}/users/{user.id}/toggle_status/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.status, "inactive")

    def test_admin_cannot_delete_self(self):
        self.auth(self.admin)
        response = self.client.delete(f"{API}/users/{self.admin.id}/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activity_log_is_admin_only(self):
        self.auth(self.admin)
        response = self.client.get(f"{API}/activity-logs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)


class ReportTests(BaseAPITestCase):
    def test_dashboard_requires_staff_and_returns_metrics(self):
        self.auth(self.customer)
        response = self.client.get(f"{API}/reports/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.auth(self.admin)
        response = self.client.get(f"{API}/reports/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data["data"]
        for key in (
            "stats",
            "revenue_analytics",
            "sales_analytic",
            "order_status_distribution",
            "best_selling_products",
            "recent_orders",
        ):
            self.assertIn(key, data)
        self.assertGreaterEqual(data["stats"]["total_products"], 1)

    def test_report_endpoints_return_data(self):
        self.auth(self.admin)
        for path in (
            f"{API}/reports/sales/",
            f"{API}/reports/products/",
            f"{API}/reports/inventory/",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("data", response.data)


class CustomerManagementTests(BaseAPITestCase):
    def test_admin_can_list_and_view_customer_orders(self):
        self.auth(self.customer)
        self.add_to_cart()
        self.place_order()

        self.auth(self.admin)
        response = self.client.get(f"{API}/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)

        response = self.client.get(f"{API}/customers/{self.customer.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.get(f"{API}/customers/{self.customer.id}/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)

    def test_admin_can_create_and_update_customer(self):
        self.auth(self.admin)
        response = self.client.post(
            f"{API}/customers/",
            {
                "email": "created.customer@test.local",
                "first_name": "Created",
                "last_name": "Customer",
                "status": "active",
                "password": "CreatedPass123!",
                "confirm_password": "CreatedPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        customer = User.objects.get(email="created.customer@test.local")
        self.assertEqual(customer.role, "customer")

        response = self.client.patch(
            f"{API}/customers/{customer.id}/",
            {"phone": "+1 555 0400"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        customer.refresh_from_db()
        self.assertEqual(customer.phone, "+1 555 0400")
