from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    message = "Administrator access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == "admin" or request.user.is_superuser)
        )


class IsAdminOrStaff(BasePermission):
    message = "Staff access required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in ("admin", "staff") or request.user.is_superuser)
        )


class IsAdminOrStaffOrReadOnly(BasePermission):
    """Public read access; writes restricted to admin/staff."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in ("admin", "staff") or request.user.is_superuser)
        )


class IsOwnerOrAdmin(BasePermission):
    """Object owner may access; admins/staff may access everything."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.role in ("admin", "staff") or user.is_superuser:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "customer", None)
        return owner == user
