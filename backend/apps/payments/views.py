"""Stripe and PayPal payment integration.

Credentials are read from the ``Setting`` table (payment group), which is
editable from the admin Settings → Payments tab. Secret keys never leave the
server; the checkout only receives public client identifiers and short-lived
payment identifiers.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import requests
import stripe
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdminOrStaff
from apps.core.utils import get_setting, log_activity
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderStatusHistory
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer


def _stripe_settings():
    return {
        "publishable_key": (get_setting("stripe_publishable_key", "") or "").strip(),
        "secret_key": (get_setting("stripe_secret_key", "") or "").strip(),
        "webhook_secret": (get_setting("stripe_webhook_secret", "") or "").strip(),
        "currency": (get_setting("currency", "USD") or "USD").strip().lower(),
    }


def _paypal_settings():
    return {
        "client_id": (get_setting("paypal_client_id", "") or "").strip(),
        "client_secret": (get_setting("paypal_client_secret", "") or "").strip(),
        "mode": (get_setting("paypal_mode", "sandbox") or "sandbox").strip().lower(),
        "currency": (get_setting("currency", "USD") or "USD").strip().upper(),
    }


def _paypal_mode(config):
    return "live" if config["mode"] in ("live", "production") else "sandbox"


def _paypal_base_url(config):
    if _paypal_mode(config) == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


class PayPalError(Exception):
    """Raised when PayPal cannot be reached or returns an invalid response."""


def _paypal_request(config, method, path, payload=None):
    """Call the PayPal REST API and return ``(status_code, data)``."""
    base = _paypal_base_url(config)
    try:
        token_response = requests.post(
            f"{base}/v1/oauth2/token",
            auth=(config["client_id"], config["client_secret"]),
            data={"grant_type": "client_credentials"},
            timeout=20,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise PayPalError("PayPal did not return an access token.")

        response = requests.request(
            method,
            f"{base}{path}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        try:
            data = response.json()
        except ValueError:
            data = {}
        return response.status_code, data
    except requests.RequestException as exc:
        raise PayPalError("Could not reach PayPal. Please try again.") from exc


def _paypal_error_message(data, fallback="PayPal could not start the payment."):
    details = data.get("details") if isinstance(data, dict) else None
    if isinstance(details, list) and details:
        issue = details[0].get("issue") or details[0].get("description")
        if issue:
            return f"{fallback} ({issue})"
    if isinstance(data, dict) and data.get("message"):
        return f"{fallback} {data['message']}"
    return fallback


def _get_user_order(request, order_id):
    try:
        order_pk = int(order_id)
    except (TypeError, ValueError):
        return None
    order = Order.objects.filter(pk=order_pk).select_related("user").first()
    if order is None:
        return None
    if (
        order.user_id != request.user.pk
        and request.user.role not in ("admin", "staff")
        and not request.user.is_superuser
    ):
        return None
    return order


def _order_total(order):
    try:
        return Decimal(order.grand_total)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _amount_in_cents(order):
    return int(
        (Decimal(order.grand_total) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def _intent_payload(intent):
    return {
        "payment_intent_id": intent.id,
        "client_secret": intent.client_secret,
        "amount": intent.amount,
        "currency": (intent.currency or "usd").upper(),
        "status": intent.status,
    }


def _finalize_order_paid(
    order, transaction_id, gateway, currency, note, notification_message
):
    """Idempotently mark the order and its payment row as paid."""
    with transaction.atomic():
        payment = order.payments.filter(transaction_id=transaction_id).first()
        if payment is None:
            payment = order.payments.filter(status="pending").first()
        if payment is None:
            payment = Payment(
                order=order,
                transaction_id=transaction_id,
                amount=order.grand_total,
            )
        payment.transaction_id = transaction_id
        payment.payment_gateway = gateway
        payment.amount = order.grand_total
        payment.currency = currency
        payment.status = "paid"
        payment.paid_at = timezone.now()
        payment.save()

        order.payments.exclude(pk=payment.pk).filter(status="pending").update(
            status="failed"
        )

        if order.payment_status != "paid":
            order.payment_status = "paid"
            order.save(update_fields=["payment_status"])
            OrderStatusHistory.objects.create(
                order=order,
                status=order.order_status,
                note=note,
                created_by=None,
            )
            Notification.objects.create(
                user=order.user,
                title=f"Payment received for {order.order_number}",
                message=notification_message,
                type="order",
                link=f"/orders/{order.pk}",
            )
    return payment


def _mark_order_paid(order, intent, note="Stripe payment received"):
    return _finalize_order_paid(
        order,
        transaction_id=intent.id,
        gateway="stripe",
        currency=(intent.currency or "usd").upper(),
        note=note,
        notification_message=(
            "Your Stripe payment was successful. We are preparing your order."
        ),
    )


def _mark_paypal_order_paid(order, paypal_order_id, currency):
    return _finalize_order_paid(
        order,
        transaction_id=paypal_order_id,
        gateway="paypal",
        currency=currency,
        note="PayPal payment received",
        notification_message=(
            "Your PayPal payment was successful. We are preparing your order."
        ),
    )



def _mark_order_payment_failed(order, intent, note="Stripe payment failed"):
    if order.payment_status == "paid":
        return
    with transaction.atomic():
        order.payments.filter(transaction_id=intent.id).update(status="failed")
        order.payments.filter(status="pending", transaction_id__startswith="TXN-").update(
            status="failed"
        )
        if order.payment_status != "failed":
            order.payment_status = "failed"
            order.save(update_fields=["payment_status"])
            OrderStatusHistory.objects.create(
                order=order,
                status=order.order_status,
                note=note,
                created_by=None,
            )


class StripeConfigView(APIView):
    """Expose only the public Stripe configuration needed by the checkout."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = _stripe_settings()
        publishable = config["publishable_key"]
        return Response(
            {
                "success": True,
                "data": {
                    "publishable_key": publishable,
                    "enabled": bool(publishable and config["secret_key"]),
                    "mode": (
                        "live"
                        if publishable.startswith("pk_live_")
                        else "test"
                        if publishable.startswith("pk_test_")
                        else "unknown"
                    ),
                    "currency": config["currency"].upper(),
                },
            }
        )


class StripeCreateIntentView(APIView):
    """Create (or reuse) a PaymentIntent for a pending Stripe order."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        config = _stripe_settings()
        if not config["secret_key"]:
            return Response(
                {
                    "success": False,
                    "message": "Stripe is not configured. Add your keys in admin settings.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        order_id = request.data.get("order_id")
        order = Order.objects.filter(pk=order_id).select_related("user").first()
        if order is None or (
            order.user_id != request.user.pk
            and request.user.role not in ("admin", "staff")
            and not request.user.is_superuser
        ):
            return Response(
                {"success": False, "message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.payment_method != "stripe":
            return Response(
                {"success": False, "message": "This order is not set to pay with Stripe."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payment_status == "paid":
            return Response(
                {"success": False, "message": "This order has already been paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        amount = _amount_in_cents(order)
        if amount <= 0:
            return Response(
                {"success": False, "message": "This order has no payable amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = order.payments.order_by("-created_at").first()
        intent = None
        if payment and payment.transaction_id.startswith("pi_"):
            try:
                existing = stripe.PaymentIntent.retrieve(
                    payment.transaction_id, api_key=config["secret_key"]
                )
                if existing.status != "canceled" and existing.amount == amount:
                    intent = existing
            except stripe.error.StripeError:
                intent = None

        if intent is None:
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount,
                    currency=config["currency"],
                    automatic_payment_methods={"enabled": True},
                    description=f"Order {order.order_number}",
                    metadata={
                        "order_id": str(order.pk),
                        "order_number": order.order_number,
                        "user_id": str(order.user_id),
                    },
                    api_key=config["secret_key"],
                )
            except stripe.error.StripeError as exc:
                return Response(
                    {
                        "success": False,
                        "message": f"Stripe could not start the payment: {getattr(exc, 'user_message', None) or 'please try again.'}",
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        if payment is None:
            payment = Payment(
                order=order,
                transaction_id=intent.id,
                amount=order.grand_total,
            )
        payment.transaction_id = intent.id
        payment.payment_gateway = "stripe"
        payment.amount = order.grand_total
        payment.currency = config["currency"].upper()
        payment.status = "pending"
        payment.save()

        log_activity(
            request.user,
            "payment.stripe_intent_created",
            f"Stripe intent {intent.id} for {order.order_number}",
            "order",
            order.pk,
            request,
        )
        return Response(
            {
                "success": True,
                "data": {
                    **_intent_payload(intent),
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "publishable_key": config["publishable_key"],
                },
            }
        )


class StripeConfirmView(APIView):
    """Confirm a PaymentIntent after Stripe.js reports success.

    This gives the local checkout immediate feedback; the webhook is still the
    source of truth for asynchronous payment events.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        config = _stripe_settings()
        if not config["secret_key"]:
            return Response(
                {
                    "success": False,
                    "message": "Stripe is not configured. Add your keys in admin settings.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        intent_id = (request.data.get("payment_intent_id") or "").strip()
        if not intent_id.startswith("pi_"):
            return Response(
                {"success": False, "message": "A valid payment intent is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            intent = stripe.PaymentIntent.retrieve(
                intent_id, api_key=config["secret_key"]
            )
        except stripe.error.StripeError:
            return Response(
                {"success": False, "message": "Could not verify this payment with Stripe."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        order_id = (intent.metadata or {}).get("order_id")
        order = Order.objects.filter(pk=order_id).select_related("user").first()
        if order is None or (
            order.user_id != request.user.pk
            and request.user.role not in ("admin", "staff")
            and not request.user.is_superuser
        ):
            return Response(
                {"success": False, "message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if intent.status != "succeeded":
            return Response(
                {
                    "success": False,
                    "message": f"Payment is not complete (status: {intent.status}).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        expected = _amount_in_cents(order)
        if intent.amount != expected or (intent.currency or "").lower() != config["currency"]:
            return Response(
                {
                    "success": False,
                    "message": "Payment amount or currency does not match this order.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = _mark_order_paid(order, intent)
        log_activity(
            request.user,
            "payment.stripe_confirmed",
            f"Stripe payment {intent.id} confirmed for {order.order_number}",
            "order",
            order.pk,
            request,
        )
        return Response(
            {
                "success": True,
                "message": "Payment confirmed.",
                "data": {
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "payment_status": order.payment_status,
                    "payment": PaymentSerializer(payment).data,
                },
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """Stripe webhook endpoint. Configure the signing secret in admin settings."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        config = _stripe_settings()
        if not config["webhook_secret"]:
            return Response(
                {"success": False, "message": "Stripe webhook secret is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe.Webhook.construct_event(
                request.body, signature, config["webhook_secret"]
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(
                {"success": False, "message": "Invalid Stripe webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        event_type = event["type"]
        intent = event["data"]["object"]

        if event_type == "payment_intent.succeeded":
            order_id = (intent.metadata or {}).get("order_id")
            order = Order.objects.filter(pk=order_id).select_related("user").first()
            if order:
                _mark_order_paid(order, intent)
        elif event_type in ("payment_intent.payment_failed", "payment_intent.canceled"):
            order_id = (intent.metadata or {}).get("order_id")
            order = Order.objects.filter(pk=order_id).select_related("user").first()
            if order:
                _mark_order_payment_failed(
                    order, intent, note=f"Stripe payment {event_type.split('.')[-1]}"
                )

        return Response({"success": True, "data": {"received": True}})


class PayPalConfigView(APIView):
    """Expose only the public PayPal configuration needed by the checkout."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        config = _paypal_settings()
        client_id = config["client_id"]
        return Response(
            {
                "success": True,
                "data": {
                    "client_id": client_id,
                    "enabled": bool(client_id and config["client_secret"]),
                    "mode": _paypal_mode(config),
                    "currency": config["currency"],
                },
            }
        )


class PayPalCreateOrderView(APIView):
    """Create a PayPal Order for a pending PayPal checkout."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        config = _paypal_settings()
        if not config["client_id"] or not config["client_secret"]:
            return Response(
                {
                    "success": False,
                    "message": "PayPal is not configured. Add your credentials in admin settings.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        order = _get_user_order(request, request.data.get("order_id"))
        if order is None:
            return Response(
                {"success": False, "message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.payment_method != "paypal":
            return Response(
                {"success": False, "message": "This order is not set to pay with PayPal."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payment_status == "paid":
            return Response(
                {"success": False, "message": "This order has already been paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total = _order_total(order)
        if total <= 0:
            return Response(
                {"success": False, "message": "This order has no payable amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": order.order_number,
                    "custom_id": str(order.pk),
                    "description": f"Order {order.order_number}",
                    "amount": {
                        "currency_code": config["currency"],
                        "value": f"{total:.2f}",
                    },
                }
            ],
            "application_context": {
                "brand_name": get_setting(
                    "site_name", "TorqueForge Industrial Supply"
                ),
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
            },
        }

        try:
            status_code, data = _paypal_request(
                config, "POST", "/v2/checkout/orders", payload
            )
        except PayPalError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if status_code >= 400 or not data.get("id"):
            return Response(
                {
                    "success": False,
                    "message": _paypal_error_message(data),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        paypal_order_id = data["id"]
        payment = order.payments.order_by("-created_at").first()
        if payment is None:
            payment = Payment(
                order=order,
                transaction_id=paypal_order_id,
                amount=order.grand_total,
            )
        payment.transaction_id = paypal_order_id
        payment.payment_gateway = "paypal"
        payment.amount = order.grand_total
        payment.currency = config["currency"]
        payment.status = "pending"
        payment.save()

        log_activity(
            request.user,
            "payment.paypal_order_created",
            f"PayPal order {paypal_order_id} for {order.order_number}",
            "order",
            order.pk,
            request,
        )

        return Response(
            {
                "success": True,
                "data": {
                    "paypal_order_id": paypal_order_id,
                    "status": data.get("status", "CREATED"),
                    "amount": f"{total:.2f}",
                    "currency": config["currency"],
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "client_id": config["client_id"],
                    "mode": _paypal_mode(config),
                },
            }
        )


class PayPalCaptureView(APIView):
    """Capture an approved PayPal Order and mark the order as paid."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        config = _paypal_settings()
        if not config["client_id"] or not config["client_secret"]:
            return Response(
                {
                    "success": False,
                    "message": "PayPal is not configured. Add your credentials in admin settings.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        order = _get_user_order(request, request.data.get("order_id"))
        if order is None:
            return Response(
                {"success": False, "message": "Order not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.payment_method != "paypal":
            return Response(
                {"success": False, "message": "This order is not set to pay with PayPal."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order.payment_status == "paid":
            return Response(
                {"success": False, "message": "This order has already been paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paypal_order_id = (request.data.get("paypal_order_id") or "").strip()
        if not paypal_order_id:
            return Response(
                {"success": False, "message": "A PayPal order id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            status_code, data = _paypal_request(
                config,
                "POST",
                f"/v2/checkout/orders/{paypal_order_id}/capture",
                {},
            )
            if status_code >= 400:
                # The order may already have been captured (for example after a
                # retry or a page refresh); read its final state instead.
                _, data = _paypal_request(
                    config, "GET", f"/v2/checkout/orders/{paypal_order_id}"
                )
        except PayPalError as exc:
            return Response(
                {"success": False, "message": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if data.get("status") != "COMPLETED":
            return Response(
                {
                    "success": False,
                    "message": (
                        "PayPal payment is not complete "
                        f"(status: {data.get('status', 'UNKNOWN')})."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        purchase_units = data.get("purchase_units") or []
        unit = purchase_units[0] if purchase_units else {}
        custom_id = str(unit.get("custom_id") or "")
        if custom_id and custom_id != str(order.pk):
            return Response(
                {
                    "success": False,
                    "message": "This PayPal payment does not belong to this order.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        reference_id = unit.get("reference_id")
        if reference_id and reference_id != order.order_number:
            return Response(
                {
                    "success": False,
                    "message": "This PayPal payment does not belong to this order.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        captures = (unit.get("payments") or {}).get("captures") or []
        capture = captures[0] if captures else {}
        amount_data = capture.get("amount") or unit.get("amount") or {}
        try:
            captured_amount = Decimal(str(amount_data.get("value")))
        except (InvalidOperation, TypeError):
            return Response(
                {
                    "success": False,
                    "message": "Could not verify the PayPal payment amount.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        captured_currency = (amount_data.get("currency_code") or "").upper()

        if (
            captured_amount != _order_total(order)
            or captured_currency != config["currency"]
        ):
            return Response(
                {
                    "success": False,
                    "message": "Payment amount or currency does not match this order.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = _mark_paypal_order_paid(order, paypal_order_id, config["currency"])
        log_activity(
            request.user,
            "payment.paypal_captured",
            f"PayPal payment {paypal_order_id} captured for {order.order_number}",
            "order",
            order.pk,
            request,
        )

        return Response(
            {
                "success": True,
                "message": "Payment confirmed.",
                "data": {
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "payment_status": order.payment_status,
                    "payment": PaymentSerializer(payment).data,
                },
            }
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("order", "order__user")
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["status", "payment_gateway"]
    search_fields = ["transaction_id", "order__order_number", "order__user__email"]
    ordering_fields = ["created_at", "amount", "status"]
    ordering = ["-created_at"]

    def update(self, request, *args, **kwargs):
        payment = self.get_object()
        new_status = request.data.get("status", payment.status)
        payment.status = new_status
        if new_status == "paid":
            payment.paid_at = timezone.now()
        payment.save()
        if new_status in ("paid", "refunded", "failed"):
            payment.order.payment_status = new_status
            payment.order.save(update_fields=["payment_status"])
        return Response(
            {
                "success": True,
                "message": "Payment updated.",
                "data": PaymentSerializer(payment).data,
            }
        )

    @action(detail=False, methods=["get"])
    def stats(self, request):
        qs = Payment.objects.all()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "paid": qs.filter(status="paid").count(),
                    "pending": qs.filter(status="pending").count(),
                    "failed": qs.filter(status="failed").count(),
                    "refunded": qs.filter(status="refunded").count(),
                },
            }
        )
