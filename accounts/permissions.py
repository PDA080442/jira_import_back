"""DRF permission classes for accounts."""
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated


class IsEmailVerified(BasePermission):
    """
    Requires authenticated user with is_active=True.
    Reserved for future /api/jira/* endpoints; login already enforces verified users.
    """

    message = "Email is not verified."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active)


__all__ = ["AllowAny", "IsAuthenticated", "IsEmailVerified"]
