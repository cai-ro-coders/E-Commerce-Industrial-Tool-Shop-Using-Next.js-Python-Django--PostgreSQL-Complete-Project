from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentViewSet,
    PayPalCaptureView,
    PayPalConfigView,
    PayPalCreateOrderView,
    StripeConfigView,
    StripeConfirmView,
    StripeCreateIntentView,
    StripeWebhookView,
)

router = DefaultRouter()
router.register("payments", PaymentViewSet, basename="payments")

urlpatterns = [
    path("payments/stripe/config/", StripeConfigView.as_view(), name="stripe-config"),
    path(
        "payments/stripe/create-intent/",
        StripeCreateIntentView.as_view(),
        name="stripe-create-intent",
    ),
    path(
        "payments/stripe/confirm/",
        StripeConfirmView.as_view(),
        name="stripe-confirm",
    ),
    path(
        "payments/stripe/webhook/",
        StripeWebhookView.as_view(),
        name="stripe-webhook",
    ),
    path("payments/paypal/config/", PayPalConfigView.as_view(), name="paypal-config"),
    path(
        "payments/paypal/create-order/",
        PayPalCreateOrderView.as_view(),
        name="paypal-create-order",
    ),
    path(
        "payments/paypal/capture/",
        PayPalCaptureView.as_view(),
        name="paypal-capture",
    ),
    path("", include(router.urls)),
]
