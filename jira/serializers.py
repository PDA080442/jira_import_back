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


class JiraIssueTypeSerializer(serializers.Serializer):
    jira_id = serializers.CharField()
    name = serializers.CharField()
    hierarchy_level = serializers.IntegerField(allow_null=True)
    is_subtask = serializers.BooleanField()
    description = serializers.CharField()
    icon_url = serializers.CharField()


class JiraFieldSerializer(serializers.Serializer):
    jira_id = serializers.CharField()
    key = serializers.CharField()
    name = serializers.CharField()
    is_custom = serializers.BooleanField()
    schema_type = serializers.CharField()
    is_required = serializers.BooleanField()
    template_field_type = serializers.CharField()
    extra = serializers.JSONField()


class JiraSprintSerializer(serializers.Serializer):
    jira_sprint_id = serializers.CharField()
    name = serializers.CharField()
    state = serializers.CharField()
    start_date = serializers.DateTimeField(allow_null=True)
    end_date = serializers.DateTimeField(allow_null=True)
    goal = serializers.CharField()
    board_id = serializers.CharField()


class JiraBoardSerializer(serializers.Serializer):
    jira_board_id = serializers.CharField()
    name = serializers.CharField()
    board_type = serializers.CharField()
    sprints = JiraSprintSerializer(many=True)


class JiraMetadataItemSerializer(serializers.Serializer):
    jira_id = serializers.CharField()
    name = serializers.CharField()
    extra = serializers.JSONField()


class JiraProjectMetadataSerializer(serializers.Serializer):
    connection_id = serializers.UUIDField()
    project_id = serializers.CharField()
    project_name = serializers.CharField()
    project_key = serializers.CharField()
    status = serializers.ChoiceField(choices=["pending", "syncing", "fresh", "failed"])
    is_stale = serializers.BooleanField()
    fetched_at = serializers.DateTimeField(allow_null=True)
    ttl_seconds = serializers.IntegerField()
    last_sync_started_at = serializers.DateTimeField(allow_null=True)
    last_error = serializers.CharField()
    issue_types = JiraIssueTypeSerializer(many=True)
    fields = JiraFieldSerializer(many=True)
    priorities = JiraMetadataItemSerializer(many=True)
    statuses = JiraMetadataItemSerializer(many=True)
    components = JiraMetadataItemSerializer(many=True)
    labels = JiraMetadataItemSerializer(many=True)
    boards = JiraBoardSerializer(many=True)

    def to_representation(self, metadata):
        from jira.models import JiraMetadataItemKind

        items = list(metadata.items.all())
        boards = []
        for board in metadata.boards.all():
            boards.append(
                {
                    "jira_board_id": board.jira_board_id,
                    "name": board.name,
                    "board_type": board.board_type,
                    "sprints": [
                        {
                            "jira_sprint_id": sprint.jira_sprint_id,
                            "name": sprint.name,
                            "state": sprint.state,
                            "start_date": sprint.start_date,
                            "end_date": sprint.end_date,
                            "goal": sprint.goal,
                            "board_id": board.jira_board_id,
                        }
                        for sprint in board.sprints.all()
                    ],
                },
            )

        def items_by_kind(kind):
            return [
                {"jira_id": item.jira_id, "name": item.name, "extra": item.extra or {}}
                for item in items
                if item.kind == kind
            ]

        return {
            "connection_id": metadata.connection_id,
            "project_id": metadata.project_id,
            "project_name": metadata.project_name,
            "project_key": metadata.project_key or metadata.connection.project_key,
            "status": metadata.status,
            "is_stale": metadata.is_stale,
            "fetched_at": metadata.fetched_at,
            "ttl_seconds": metadata.ttl_seconds,
            "last_sync_started_at": metadata.last_sync_started_at,
            "last_error": metadata.last_error,
            "issue_types": [
                {
                    "jira_id": issue_type.jira_id,
                    "name": issue_type.name,
                    "hierarchy_level": issue_type.hierarchy_level,
                    "is_subtask": issue_type.is_subtask,
                    "description": issue_type.description,
                    "icon_url": issue_type.icon_url,
                }
                for issue_type in metadata.issue_types.all()
            ],
            "fields": [
                {
                    "jira_id": field.jira_id,
                    "key": field.key,
                    "name": field.name,
                    "is_custom": field.is_custom,
                    "schema_type": field.schema_type,
                    "is_required": field.is_required,
                    "template_field_type": field.template_field_type,
                    "extra": field.extra or {},
                }
                for field in metadata.fields.all()
            ],
            "priorities": items_by_kind(JiraMetadataItemKind.PRIORITY),
            "statuses": items_by_kind(JiraMetadataItemKind.STATUS),
            "components": items_by_kind(JiraMetadataItemKind.COMPONENT),
            "labels": items_by_kind(JiraMetadataItemKind.LABEL),
            "boards": boards,
        }


class JiraMetadataSyncResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "syncing", "fresh", "failed"])
    detail = serializers.CharField()


class JiraGuideSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    title = serializers.CharField()
    summary = serializers.CharField()
    locale = serializers.CharField()
    version = serializers.IntegerField()
    content = serializers.JSONField()
    updated_at = serializers.DateTimeField()


class JiraGuideListItemSerializer(serializers.Serializer):
    slug = serializers.SlugField()
    title = serializers.CharField()
    summary = serializers.CharField()
    locale = serializers.CharField()
    version = serializers.IntegerField()
    updated_at = serializers.DateTimeField()
