"""OpenAPI schema helpers for auth and profile endpoints."""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers

from accounts.serializers import (
    LoginSerializer,
    LogoutSerializer,
    PasswordConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileSerializer,
    RegisterSerializer,
    VerifyEmailSerializer,
)
from core.openapi import (
    API_ERROR_400,
    API_ERROR_401,
    API_ERROR_403,
    MESSAGE_RESPONSE,
    PUBLIC_ERRORS,
    TRACE_ID_HEADER,
    error_response,
)

RegisterResponseSerializer = inline_serializer(
    name="RegisterResponse",
    fields={
        "id": serializers.UUIDField(help_text="Created user UUID."),
        "email": serializers.EmailField(help_text="Normalized email address."),
    },
)

TokenPairResponseSerializer = inline_serializer(
    name="TokenPairResponse",
    fields={
        "access": serializers.CharField(help_text="JWT access token (default TTL: 15 minutes)."),
        "refresh": serializers.CharField(help_text="JWT refresh token (default TTL: 7 days)."),
    },
)

RefreshTokenRequestSerializer = inline_serializer(
    name="RefreshTokenRequest",
    fields={
        "refresh": serializers.CharField(help_text="Valid refresh token from login response."),
    },
)

RefreshTokenResponseSerializer = inline_serializer(
    name="RefreshTokenResponse",
    fields={
        "access": serializers.CharField(help_text="New JWT access token."),
    },
)

INVALID_CREDENTIALS_EXAMPLE = OpenApiExample(
    name="Invalid credentials",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "INVALID_CREDENTIALS",
        "message": "Invalid email or password.",
        "fieldErrors": {},
    },
    response_only=True,
)

EMAIL_NOT_VERIFIED_EXAMPLE = OpenApiExample(
    name="Email not verified",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "EMAIL_NOT_VERIFIED",
        "message": "Email address is not verified.",
        "fieldErrors": {},
    },
    response_only=True,
)

TOKEN_INVALID_EXAMPLE = OpenApiExample(
    name="Invalid token",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "TOKEN_INVALID",
        "message": "Invalid or already used token.",
        "fieldErrors": {},
    },
    response_only=True,
)

AUTH_TAG = "Auth"
PROFILE_TAG = "Profile"

register_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_register",
    summary="Register a new user",
    auth=[],
    description=(
        "Creates an **inactive** user account and queues a verification email (Celery). "
        "JWT tokens are **not** returned — call verify-email, then login."
    ),
    request=RegisterSerializer,
    responses={
        201: OpenApiResponse(
            response=RegisterResponseSerializer,
            description="User created; verification email queued.",
            examples=[
                OpenApiExample(
                    name="Created",
                    value={"id": "550e8400-e29b-41d4-a716-446655440000", "email": "user@example.com"},
                    response_only=True,
                ),
            ],
        ),
        **PUBLIC_ERRORS,
    },
    examples=[
        OpenApiExample(
            name="Register",
            value={
                "email": "user@example.com",
                "password": "password12345",
                "password_confirm": "password12345",
            },
            request_only=True,
        ),
    ],
)

verify_email_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_verify_email",
    summary="Verify email address",
    auth=[],
    description=(
        "Activates the user account using the token from the verification email. "
        "Token is single-use; expired tokens return `TOKEN_EXPIRED`."
    ),
    request=VerifyEmailSerializer,
    responses={
        200: OpenApiResponse(
            response=MESSAGE_RESPONSE,
            description="Email verified; user can log in.",
        ),
        400: error_response(
            400,
            "Invalid or expired verification token.",
            examples=[TOKEN_INVALID_EXAMPLE],
        ),
    },
    examples=[
        OpenApiExample(
            name="Verify",
            value={"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."},
            request_only=True,
        ),
    ],
)

login_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_login",
    summary="Login and obtain JWT",
    auth=[],
    description=(
        "Returns access + refresh token pair for a verified, active user. "
        "Unverified users receive 403 `EMAIL_NOT_VERIFIED`."
    ),
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            response=TokenPairResponseSerializer,
            description="JWT token pair.",
        ),
        401: error_response(
            401,
            "Wrong email or password.",
            examples=[INVALID_CREDENTIALS_EXAMPLE],
        ),
        403: error_response(
            403,
            "Account exists but email is not verified.",
            examples=[EMAIL_NOT_VERIFIED_EXAMPLE],
        ),
    },
)

logout_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_logout",
    summary="Logout (blacklist refresh token)",
    auth=[],
    description="Blacklists the given refresh token. Access token remains valid until expiry.",
    request=LogoutSerializer,
    responses={
        204: OpenApiResponse(description="Refresh token blacklisted."),
        400: error_response(400, "Invalid refresh token.", examples=[TOKEN_INVALID_EXAMPLE]),
    },
)

password_reset_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_password_reset",
    summary="Request password reset email",
    auth=[],
    description=(
        "Always returns 200 with a generic message (no email enumeration). "
        "If the account exists, a reset link is queued via Celery."
    ),
    request=PasswordResetRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=MESSAGE_RESPONSE,
            description="Generic success message.",
        ),
        **PUBLIC_ERRORS,
    },
)

password_confirm_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_password_confirm",
    summary="Confirm password reset",
    auth=[],
    description="Sets a new password using the token from the reset email.",
    request=PasswordConfirmSerializer,
    responses={
        200: OpenApiResponse(response=MESSAGE_RESPONSE, description="Password updated."),
        400: error_response(
            400,
            "Invalid/expired token or validation error.",
            examples=[TOKEN_INVALID_EXAMPLE],
        ),
    },
)

refresh_schema = extend_schema(
    tags=[AUTH_TAG],
    operation_id="auth_refresh",
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access token.",
    auth=[],
    request=RefreshTokenRequestSerializer,
    responses={
        200: OpenApiResponse(response=RefreshTokenResponseSerializer, description="New access token."),
        401: API_ERROR_401,
    },
)

me_get_schema = extend_schema(
    tags=[PROFILE_TAG],
    operation_id="profile_get",
    summary="Get current user profile",
    description="Returns profile for the authenticated user only.",
    parameters=[TRACE_ID_HEADER],
    responses={
        200: ProfileSerializer,
        401: API_ERROR_401,
    },
)

me_patch_schema = extend_schema(
    tags=[PROFILE_TAG],
    operation_id="profile_update",
    summary="Update current user profile",
    description="Partial update of locale, timezone, and notification preferences.",
    parameters=[TRACE_ID_HEADER],
    request=ProfileSerializer,
    responses={
        200: ProfileSerializer,
        400: API_ERROR_400,
        401: API_ERROR_401,
    },
)
