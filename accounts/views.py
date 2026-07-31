"""Thin DRF views: validate request, delegate to services, return Response."""
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.openapi import (
    login_schema,
    logout_schema,
    me_get_schema,
    me_patch_schema,
    password_confirm_schema,
    password_reset_schema,
    refresh_schema,
    register_schema,
    verify_email_schema,
)
from accounts.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
    VerifyEmailSerializer,
)
from accounts.services import auth as auth_service
from accounts.services import profile as profile_service


class PublicAuthView(APIView):
    """Public auth endpoints: no JWT required (explicit override of global defaults)."""

    authentication_classes = []
    permission_classes = [AllowAny]


@extend_schema_view(post=register_schema)
class RegisterView(PublicAuthView):
    """POST /api/auth/register/ — create inactive user and send verification email."""

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = auth_service.register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(
            {"id": str(user.id), "email": user.email},
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(post=verify_email_schema)
class VerifyEmailView(PublicAuthView):
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        auth_service.verify_user_email(raw_token=serializer.validated_data["token"])
        return Response({"message": "Email verified successfully."})


@extend_schema_view(post=login_schema)
class LoginView(PublicAuthView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = auth_service.login_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(tokens)


@extend_schema_view(post=logout_schema)
class LogoutView(PublicAuthView):
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        auth_service.logout_user(
            refresh_token=serializer.validated_data["refresh"],
            user=user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(post=password_reset_schema)
class PasswordResetView(PublicAuthView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        auth_service.request_password_reset(email=serializer.validated_data["email"])
        return Response({"message": "If the email exists, a reset link has been sent."})


@extend_schema_view(post=password_confirm_schema)
class PasswordConfirmView(PublicAuthView):
    def post(self, request):
        serializer = PasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        auth_service.reset_password(
            raw_token=serializer.validated_data["token"],
            password=serializer.validated_data["password"],
        )
        return Response({"message": "Password has been reset."})


@extend_schema_view(get=me_get_schema, patch=me_patch_schema)
class MeView(APIView):
    """GET/PATCH /api/me/ — own profile only (object scope = request.user)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = profile_service.get_profile(request.user)
        return Response(ProfileSerializer(profile).data)

    def patch(self, request):
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = profile_service.update_profile(request.user, data=serializer.validated_data)
        return Response(ProfileSerializer(profile).data)


@extend_schema_view(post=refresh_schema)
class RefreshTokenView(TokenRefreshView):
    authentication_classes = []
    permission_classes = [AllowAny]
