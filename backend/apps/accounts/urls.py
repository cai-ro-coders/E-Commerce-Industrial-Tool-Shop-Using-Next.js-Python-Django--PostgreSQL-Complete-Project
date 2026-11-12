from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from apps.accounts.views import (
    AccountSummaryView,
    ActivityLogViewSet,
    AddressViewSet,
    ChangePasswordView,
    ForgotPasswordView,
    LoginHistoryView,
    LoginView,
    LogoutView,
    ProfileView,
    RegisterView,
    ResetPasswordView,
    UserViewSet,
)

router = DefaultRouter()
router.register("users", UserViewSet, basename="users")
router.register("addresses", AddressViewSet, basename="addresses")
router.register("activity-logs", ActivityLogViewSet, basename="activity-logs")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/verify/", TokenVerifyView.as_view(), name="auth-verify"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/profile/", ProfileView.as_view(), name="auth-profile"),
    path("auth/me/", ProfileView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    path("auth/login-history/", LoginHistoryView.as_view(), name="auth-login-history"),
    path("auth/account-summary/", AccountSummaryView.as_view(), name="auth-account-summary"),
    path("", include(router.urls)),
]
