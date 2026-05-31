"""URL routes for auth and profile API under /api/."""
from django.urls import path

from accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    PasswordConfirmView,
    PasswordResetView,
    RefreshTokenView,
    RegisterView,
    VerifyEmailView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="auth-verify-email"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="auth-refresh"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/password/reset/", PasswordResetView.as_view(), name="auth-password-reset"),
    path("auth/password/confirm/", PasswordConfirmView.as_view(), name="auth-password-confirm"),
    path("me/", MeView.as_view(), name="me"),
]
