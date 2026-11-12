from datetime import timedelta

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.core.mail import send_mail
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import (
    ActivityLog,
    Address,
    LoginHistory,
    PasswordResetToken,
    User,
)
from apps.accounts.serializers import (
    ActivityLogSerializer,
    AddressSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginHistorySerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserListSerializer,
    UserSerializer,
)
from apps.cart.models import Cart, Wishlist
from apps.core.mixins import EnvelopeCreateMixin, EnvelopeListMixin
from apps.core.permissions import IsAdmin, IsAdminOrStaff
from apps.core.utils import client_ip, log_activity
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.orders.serializers import OrderListSerializer


def token_payload(user, remember_me=False):
    refresh = LoginSerializer.get_token(user)
    if remember_me:
        refresh.set_exp(lifetime=timedelta(days=30))
    access = refresh.access_token
    return {
        "access": str(access),
        "refresh": str(refresh),
        "user": UserListSerializer(user).data,
    }


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            email = str(request.data.get("email", ""))[:254]
            user = User.objects.filter(email__iexact=email).first()
            LoginHistory.objects.create(
                user=user,
                email=email,
                ip_address=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
                success=False,
            )
            message = serializer.errors.get("non_field_errors", ["Login failed."])[0]
            return Response(
                {"success": False, "message": str(message), "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        remember = serializer.validated_data.get("remember_me", False)
        user.last_login = timezone.now()
        user.last_login_ip = client_ip(request)
        user.save(update_fields=["last_login", "last_login_ip"])

        LoginHistory.objects.create(
            user=user,
            email=user.email,
            ip_address=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:400],
            success=True,
        )
        log_activity(user, "auth.login", "User signed in", "user", user.pk, request)
        return Response(
            {
                "success": True,
                "message": f"Welcome back, {user.full_name}!",
                "data": token_payload(user, remember),
            }
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            log_activity(user, "auth.register", "New customer registered", "user", user.pk, request)
            return Response(
                {
                    "success": True,
                    "message": "Account created successfully.",
                    "data": token_payload(user),
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"success": False, "message": "Please check the form.", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass
        log_activity(request.user, "auth.logout", "User signed out", "user", request.user.pk, request)
        return Response({"success": True, "message": "You have been signed out."})


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        return Response(
            {
                "success": True,
                "data": ProfileSerializer(request.user, context={"request": request}).data,
            }
        )

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            log_activity(request.user, "profile.updated", "Profile updated", "user", request.user.pk, request)
            return Response(
                {"success": True, "message": "Profile updated.", "data": serializer.data}
            )
        return Response(
            {"success": False, "message": "Please check the form.", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data["new_password"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            log_activity(request.user, "auth.password_changed", "Password changed", "user", request.user.pk, request)
            return Response({"success": True, "message": "Password changed successfully."})
        return Response(
            {"success": False, "message": "Password change failed.", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Invalid email.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email=email, status="active").first()
        extra = {}
        if user:
            token = PasswordResetToken.objects.create(
                user=user, expires_at=timezone.now() + timedelta(hours=1)
            )
            link = f"{settings.FRONTEND_URL}/reset-password?token={token.token}"
            send_mail(
                "Reset your password",
                f"Hello {user.full_name},\n\nReset your password using this link:\n{link}\n\n"
                "This link expires in 1 hour. If you did not request it, ignore this email.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
            log_activity(user, "auth.password_reset_requested", "Password reset requested", "user", user.pk, request)
            if settings.DEBUG:
                extra = {"reset_token": str(token.token), "reset_link": link}
        return Response(
            {
                "success": True,
                "message": "If an account exists for that email, a reset link has been sent.",
                "data": extra,
            }
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "message": "Please check the form.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = PasswordResetToken.objects.filter(
            token=serializer.validated_data["token"]
        ).select_related("user").first()
        if not token or not token.is_valid:
            return Response(
                {"success": False, "message": "This reset link is invalid or has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = token.user
        user.set_password(serializer.validated_data["password"])
        user.save()
        token.used = True
        token.save(update_fields=["used"])
        log_activity(user, "auth.password_reset", "Password reset completed", "user", user.pk, request)
        return Response({"success": True, "message": "Password reset successfully. You can now sign in."})


class LoginHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = LoginHistory.objects.select_related("user")
        if request.user.role not in ("admin", "staff"):
            qs = qs.filter(user=request.user)
        qs = qs[:100]
        return Response({"success": True, "data": LoginHistorySerializer(qs, many=True).data})


class AccountSummaryView(APIView):
    """Aggregated dashboard data for the customer account page."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        orders = Order.objects.filter(user=user)
        cart = Cart.objects.filter(user=user).prefetch_related("items").first()
        total_spent = (
            orders.filter(payment_status="paid").aggregate(total=Sum("grand_total"))["total"]
            or 0
        )
        recent_orders = (
            orders.select_related("user")
            .prefetch_related("items__product__images")
            .order_by("-created_at")[:5]
        )
        return Response(
            {
                "success": True,
                "data": {
                    "total_orders": orders.count(),
                    "pending_orders": orders.filter(
                        order_status__in=("pending", "processing")
                    ).count(),
                    "wishlist_items": Wishlist.objects.filter(user=user).count(),
                    "cart_items": cart.item_count if cart else 0,
                    "total_spent": total_spent,
                    "unread_notifications": Notification.objects.filter(
                        user=user, is_read=False
                    ).count(),
                    "recent_orders": OrderListSerializer(
                        recent_orders, many=True, context={"request": request}
                    ).data,
                },
            }
        )


class AddressViewSet(EnvelopeListMixin, EnvelopeCreateMixin, viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = Address.objects.all()
        if user.role not in ("admin", "staff"):
            qs = qs.filter(user=user)
        user_id = self.request.query_params.get("user")
        if user_id and user.role in ("admin", "staff"):
            qs = qs.filter(user_id=user_id)
        return qs

    def perform_create(self, serializer):
        user_id = self.request.data.get("user")
        user = self.request.user
        if user.role in ("admin", "staff") and user_id:
            user = User.objects.get(pk=user_id)
        serializer.save(user=user)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ["role", "status", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["date_joined", "email", "role", "status"]
    ordering = ["-date_joined"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAdminOrStaff()]
        return [IsAdmin()]

    def get_serializer_class(self):
        if self.action == "list":
            return UserListSerializer
        return UserSerializer

    def get_queryset(self):
        return (
            User.objects.annotate(
                orders_count=Count("orders", distinct=True),
                total_spent=Sum("orders__grand_total", filter=Q(orders__payment_status="paid")),
            )
            .order_by("-date_joined")
        )

    def perform_update(self, serializer):
        user = serializer.save()
        log_activity(self.request.user, "user.updated", f"Updated user {user.email}", "user", user.pk, self.request)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("You cannot delete your own account.")
        log_activity(self.request.user, "user.deleted", f"Deleted user {instance.email}", "user", instance.pk, self.request)
        instance.delete()

    @action(detail=True, methods=["patch"], permission_classes=[IsAdminOrStaff])
    def toggle_status(self, request, pk=None):
        user = self.get_object()
        user.status = "inactive" if user.status == "active" else "active"
        user.is_active = user.status == "active"
        user.save(update_fields=["status", "is_active"])
        log_activity(request.user, "user.status_changed", f"{user.email} set to {user.status}", "user", user.pk, request)
        return Response({"success": True, "message": f"Account {user.status}.", "data": {"status": user.status}})

    @action(detail=False, methods=["get"], permission_classes=[IsAdminOrStaff])
    def stats(self, request):
        qs = User.objects.all()
        return Response(
            {
                "success": True,
                "data": {
                    "total": qs.count(),
                    "admins": qs.filter(role="admin").count(),
                    "staff": qs.filter(role="staff").count(),
                    "customers": qs.filter(role="customer").count(),
                    "active": qs.filter(status="active").count(),
                    "inactive": qs.exclude(status="active").count(),
                },
            }
        )


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActivityLog.objects.select_related("user")
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ["action", "entity_type", "user"]
    search_fields = ["action", "description", "entity_id", "user__email"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
