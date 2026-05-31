"""DRF permission classes for accounts (extend here for IsEmailVerified, etc.)."""
from rest_framework.permissions import AllowAny, IsAuthenticated

__all__ = ["AllowAny", "IsAuthenticated"]
