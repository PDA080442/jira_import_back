"""DRF serializers for Jira connection API."""
import re

from rest_framework import serializers

from jira.constants import (
    MAX_BASE_URL_LENGTH,
    MAX_BOARD_ID_LENGTH,
    MAX_CONNECTION_NAME_LENGTH,
    MAX_PROJECT_KEY_LENGTH,
    MIN_CONNECTION_NAME_LENGTH,
    PROJECT_KEY_PATTERN,
)
from jira.models import JiraConnection


def validate_https_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith("https://"):
        raise serializers.ValidationError("base_url must use HTTPS.")
    if len(value) > MAX_BASE_URL_LENGTH:
        raise serializers.ValidationError("base_url is too long.")
    return value


def validate_project_key(value: str) -> str:
    value = value.strip().upper()
    if not re.match(PROJECT_KEY_PATTERN, value):
        raise serializers.ValidationError(
            "project_key must start with a letter and contain only A-Z, 0-9, underscore.",
        )
    if len(value) > MAX_PROJECT_KEY_LENGTH:
        raise serializers.ValidationError("project_key is too long.")
    return value


class JiraConnectionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(
        min_length=MIN_CONNECTION_NAME_LENGTH,
        max_length=MAX_CONNECTION_NAME_LENGTH,
        help_text="Unique connection name within workspace.",
    )
    base_url = serializers.CharField(
        max_length=MAX_BASE_URL_LENGTH,
        help_text="Jira Cloud site URL, e.g. https://your-domain.atlassian.net",
    )
    email = serializers.EmailField(help_text="Atlassian account email for API token auth.")
    api_token = serializers.CharField(
        write_only=True,
        help_text="Jira API token; stored encrypted, never returned in responses.",
    )
    project_key = serializers.CharField(
        max_length=MAX_PROJECT_KEY_LENGTH,
        help_text="Default Jira project key, e.g. PROJ.",
    )
    board_id = serializers.CharField(
        max_length=MAX_BOARD_ID_LENGTH,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional Jira board id for agile workflows.",
    )
    extra = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Additional connection parameters (JSON object).",
    )
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_base_url(self, value):
        return validate_https_base_url(value)

    def validate_project_key(self, value):
        return validate_project_key(value)

    def validate_api_token(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("API token is required.")
        return value.strip()


class JiraConnectionUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(
        min_length=MIN_CONNECTION_NAME_LENGTH,
        max_length=MAX_CONNECTION_NAME_LENGTH,
        required=False,
    )
    base_url = serializers.CharField(max_length=MAX_BASE_URL_LENGTH, required=False)
    email = serializers.EmailField(required=False)
    api_token = serializers.CharField(write_only=True, required=False)
    project_key = serializers.CharField(max_length=MAX_PROJECT_KEY_LENGTH, required=False)
    board_id = serializers.CharField(max_length=MAX_BOARD_ID_LENGTH, required=False, allow_blank=True)
    extra = serializers.JSONField(required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_base_url(self, value):
        return validate_https_base_url(value)

    def validate_project_key(self, value):
        return validate_project_key(value)

    def validate_api_token(self, value):
        if value is not None and not value.strip():
            raise serializers.ValidationError("API token cannot be empty.")
        return value.strip() if value else value


class JiraConnectionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    workspace_id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    base_url = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    project_key = serializers.CharField(read_only=True)
    board_id = serializers.CharField(read_only=True)
    extra = serializers.JSONField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    has_api_token = serializers.BooleanField(read_only=True)
    last_test_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_test_status = serializers.CharField(read_only=True)
    last_test_error = serializers.CharField(read_only=True)
    created_by_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def to_representation(self, connection: JiraConnection):
        return {
            "id": connection.id,
            "workspace_id": connection.workspace_id,
            "name": connection.name,
            "base_url": connection.base_url,
            "email": connection.email,
            "project_key": connection.project_key,
            "board_id": connection.board_id,
            "extra": connection.extra or {},
            "is_active": connection.is_active,
            "has_api_token": bool(connection.api_token_encrypted),
            "last_test_at": connection.last_test_at,
            "last_test_status": connection.last_test_status,
            "last_test_error": connection.last_test_error,
            "created_by_id": connection.created_by_id,
            "created_at": connection.created_at,
            "updated_at": connection.updated_at,
        }


class JiraConnectionAccountSerializer(serializers.Serializer):
    account_id = serializers.CharField()
    display_name = serializers.CharField()
    email_address = serializers.CharField()


class JiraConnectionTestResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["unknown", "success", "failed"])
    tested_at = serializers.DateTimeField()
    detail = serializers.CharField()
    account = JiraConnectionAccountSerializer(allow_null=True, required=False)
