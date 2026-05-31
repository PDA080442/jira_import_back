"""DRF serializers: input validation only; business rules live in services."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers

from accounts.constants import MIN_PASSWORD_LENGTH
from accounts.models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=MIN_PASSWORD_LENGTH)
    password_confirm = serializers.CharField(write_only=True, min_length=MIN_PASSWORD_LENGTH)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["Passwords do not match."]},
            )
        return attrs


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=MIN_PASSWORD_LENGTH)
    password_confirm = serializers.CharField(write_only=True, min_length=MIN_PASSWORD_LENGTH)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["Passwords do not match."]},
            )
        return attrs


class ProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    locale = serializers.CharField(max_length=16, required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    notification_preferences = serializers.JSONField(required=False)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate_timezone(self, value):
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError("Invalid timezone.") from exc
        return value

    def to_representation(self, profile):
        return {
            "id": profile.id,
            "email": profile.user.email,
            "locale": profile.locale,
            "timezone": profile.timezone,
            "notification_preferences": profile.notification_preferences,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }
