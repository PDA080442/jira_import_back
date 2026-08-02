"""OpenAPI schema helpers for Jira connection endpoints."""
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers

from core.openapi import (
    API_ERROR_400,
    API_ERROR_401,
    API_ERROR_403,
    API_ERROR_404,
    TRACE_ID_HEADER,
    error_response,
)
from jira.serializers import (
    JiraConnectionCreateSerializer,
    JiraConnectionSerializer,
    JiraConnectionTestResultSerializer,
    JiraConnectionUpdateSerializer,
    JiraGuideListItemSerializer,
    JiraGuideSerializer,
    JiraMetadataSyncResponseSerializer,
    JiraProjectMetadataSerializer,
)

JIRA_CONNECTIONS_TAG = "Jira Connections"
JIRA_METADATA_TAG = "Jira Metadata"
JIRA_GUIDES_TAG = "Jira Guides"

GUIDE_SLUG_PATH = OpenApiParameter(
    name="slug",
    type=str,
    location=OpenApiParameter.PATH,
    description="Guide slug, e.g. jira-connection-setup.",
)

WORKSPACE_ID_PATH = OpenApiParameter(
    name="workspace_id",
    type=str,
    location=OpenApiParameter.PATH,
    description="Workspace UUID. Non-members receive 404 NOT_FOUND.",
)

CONNECTION_ID_PATH = OpenApiParameter(
    name="id",
    type=str,
    location=OpenApiParameter.PATH,
    description="Jira connection UUID within the workspace.",
)

FORBIDDEN_ADMIN_EXAMPLE = OpenApiExample(
    name="Not admin",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "FORBIDDEN",
        "message": "You do not have permission to manage Jira connections.",
        "fieldErrors": {},
    },
    response_only=True,
)

connection_example = OpenApiExample(
    name="Jira connection",
    value={
        "id": "990e8400-e29b-41d4-a716-446655440004",
        "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Production Jira",
        "base_url": "https://example.atlassian.net",
        "email": "admin@example.com",
        "project_key": "PROJ",
        "board_id": "42",
        "extra": {},
        "is_active": True,
        "has_api_token": True,
        "last_test_at": None,
        "last_test_status": "unknown",
        "last_test_error": "",
        "created_by_id": "660e8400-e29b-41d4-a716-446655440001",
        "created_at": "2026-07-31T12:00:00.000000Z",
        "updated_at": "2026-07-31T12:00:00.000000Z",
    },
    response_only=True,
)

test_success_example = OpenApiExample(
    name="Test success",
    value={
        "status": "success",
        "tested_at": "2026-07-31T12:05:00.000000Z",
        "detail": "Connection successful.",
        "account": {
            "account_id": "5b10a2844c20165700ede21g",
            "display_name": "Admin User",
            "email_address": "admin@example.com",
        },
    },
    response_only=True,
)

jira_connection_list_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_list",
    summary="List Jira connections",
    description="Returns all Jira connections in the workspace. Any member can read. API token is never included.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    responses={
        200: OpenApiResponse(
            response=JiraConnectionSerializer(many=True),
            examples=[connection_example],
        ),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

jira_connection_create_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_create",
    summary="Create Jira connection",
    description=(
        "Creates a Jira Cloud connection. Requires **admin** or **owner**. "
        "`api_token` is write-only and stored encrypted (Fernet)."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    request=JiraConnectionCreateSerializer,
    responses={
        201: OpenApiResponse(response=JiraConnectionSerializer, examples=[connection_example]),
        400: API_ERROR_400,
        401: API_ERROR_401,
        403: error_response(403, "Not admin/owner.", examples=[FORBIDDEN_ADMIN_EXAMPLE]),
        404: API_ERROR_404,
    },
    examples=[
        OpenApiExample(
            name="Create connection",
            value={
                "name": "Production Jira",
                "base_url": "https://example.atlassian.net",
                "email": "admin@example.com",
                "api_token": "your-api-token",
                "project_key": "PROJ",
                "board_id": "42",
                "extra": {},
            },
            request_only=True,
        ),
    ],
)

jira_connection_get_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_get",
    summary="Get Jira connection",
    description="Returns connection details without API token. Any workspace member can read.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    responses={
        200: OpenApiResponse(response=JiraConnectionSerializer, examples=[connection_example]),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

jira_connection_update_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_update",
    summary="Update Jira connection",
    description=(
        "Partial update. Requires **admin** or **owner**. "
        "Re-encrypt `api_token` only when a new value is provided. "
        "Set `is_active=true` to reactivate a deactivated connection."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    request=JiraConnectionUpdateSerializer,
    responses={
        200: OpenApiResponse(response=JiraConnectionSerializer, examples=[connection_example]),
        400: API_ERROR_400,
        401: API_ERROR_401,
        403: error_response(403, "Not admin/owner.", examples=[FORBIDDEN_ADMIN_EXAMPLE]),
        404: API_ERROR_404,
    },
)

jira_connection_deactivate_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_deactivate",
    summary="Deactivate Jira connection",
    description="Soft-deactivate (`is_active=false`). Requires **admin** or **owner**. No hard delete.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    request=None,
    responses={
        200: OpenApiResponse(
            response=JiraConnectionSerializer,
            description="Deactivated connection.",
            examples=[
                OpenApiExample(
                    name="Deactivated",
                    value={
                        **connection_example.value,
                        "is_active": False,
                    },
                    response_only=True,
                ),
            ],
        ),
        401: API_ERROR_401,
        403: error_response(403, "Not admin/owner.", examples=[FORBIDDEN_ADMIN_EXAMPLE]),
        404: API_ERROR_404,
    },
)

jira_connection_test_schema = extend_schema(
    tags=[JIRA_CONNECTIONS_TAG],
    operation_id="jira_connection_test",
    summary="Test Jira connection",
    description=(
        "Synchronous test against Jira REST `GET /rest/api/3/myself`. "
        "Requires **admin** or **owner**. Updates `last_test_*` on the connection."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    request=None,
    responses={
        200: OpenApiResponse(
            response=JiraConnectionTestResultSerializer,
            examples=[test_success_example],
        ),
        401: API_ERROR_401,
        403: error_response(403, "Not admin/owner.", examples=[FORBIDDEN_ADMIN_EXAMPLE]),
        404: API_ERROR_404,
    },
)

DeactivatedMessageSerializer = inline_serializer(
    name="JiraConnectionDeactivateResponse",
    fields={"message": serializers.CharField()},
)

guide_example = OpenApiExample(
    name="Connection setup guide",
    value={
        "slug": "jira-connection-setup",
        "title": "Подключение Jira Cloud: пошаговая инструкция",
        "summary": "Как получить API-токen, project key и подключить Jira к workspace.",
        "locale": "ru",
        "version": 1,
        "updated_at": "2026-07-31T12:00:00.000000Z",
        "content": [
            {
                "id": "intro",
                "title": "Что это и зачем",
                "blocks": [
                    {"type": "paragraph", "text": "Подключение связывает ваш workspace с проектом в Jira Cloud."},
                ],
            },
        ],
    },
    response_only=True,
)

jira_guide_list_schema = extend_schema(
    tags=[JIRA_GUIDES_TAG],
    operation_id="jira_guide_list",
    summary="List help guides",
    description="Returns published help guides (metadata only, without full content).",
    parameters=[TRACE_ID_HEADER],
    responses={
        200: OpenApiResponse(response=JiraGuideListItemSerializer(many=True)),
        401: API_ERROR_401,
    },
)

jira_guide_get_schema = extend_schema(
    tags=[JIRA_GUIDES_TAG],
    operation_id="jira_guide_get",
    summary="Get help guide by slug",
    description=(
        "Returns a published help guide with structured `content` (list of sections "
        "with typed blocks) for rendering on the frontend. "
        "Main guide: `jira-connection-setup`."
    ),
    parameters=[TRACE_ID_HEADER, GUIDE_SLUG_PATH],
    responses={
        200: OpenApiResponse(response=JiraGuideSerializer, examples=[guide_example]),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

metadata_fresh_example = OpenApiExample(
    name="Fresh metadata",
    value={
        "connection_id": "990e8400-e29b-41d4-a716-446655440004",
        "project_id": "10001",
        "project_name": "Demo Project",
        "project_key": "PROJ",
        "status": "fresh",
        "is_stale": False,
        "fetched_at": "2026-07-31T12:10:00.000000Z",
        "ttl_seconds": 3600,
        "last_sync_started_at": "2026-07-31T12:09:30.000000Z",
        "last_error": "",
        "issue_types": [
            {
                "jira_id": "10001",
                "name": "Story",
                "hierarchy_level": 0,
                "is_subtask": False,
                "description": "",
                "icon_url": "https://example.atlassian.net/icon.png",
            },
        ],
        "fields": [
            {
                "jira_id": "customfield_10001",
                "key": "summary",
                "name": "Summary",
                "is_custom": False,
                "schema_type": "string",
                "is_required": True,
                "template_field_type": "text",
                "extra": {"schema": {"type": "string"}},
            },
        ],
        "priorities": [{"jira_id": "1", "name": "Highest", "extra": {}}],
        "statuses": [{"jira_id": "3", "name": "In Progress", "extra": {}}],
        "components": [{"jira_id": "10000", "name": "Backend", "extra": {}}],
        "labels": [{"jira_id": "label-0", "name": "bug", "extra": {}}],
        "boards": [
            {
                "jira_board_id": "42",
                "name": "PROJ board",
                "board_type": "scrum",
                "sprints": [
                    {
                        "jira_sprint_id": "101",
                        "name": "Sprint 1",
                        "state": "active",
                        "start_date": "2026-07-01T00:00:00.000000Z",
                        "end_date": "2026-07-14T00:00:00.000000Z",
                        "goal": "MVP",
                        "board_id": "42",
                    },
                ],
            },
        ],
    },
    response_only=True,
)

metadata_pending_example = OpenApiExample(
    name="Pending metadata",
    value={
        "connection_id": "990e8400-e29b-41d4-a716-446655440004",
        "project_id": "",
        "project_name": "",
        "project_key": "PROJ",
        "status": "pending",
        "is_stale": True,
        "fetched_at": None,
        "ttl_seconds": 3600,
        "last_sync_started_at": None,
        "last_error": "",
        "issue_types": [],
        "fields": [],
        "priorities": [],
        "statuses": [],
        "components": [],
        "labels": [],
        "boards": [],
    },
    response_only=True,
)

metadata_sync_accepted_example = OpenApiExample(
    name="Sync accepted",
    value={"status": "syncing", "detail": "Metadata sync started."},
    response_only=True,
)

SYNC_IN_PROGRESS_EXAMPLE = OpenApiExample(
    name="Sync in progress",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "SYNC_IN_PROGRESS",
        "message": "Metadata sync is already in progress.",
        "fieldErrors": {},
    },
    response_only=True,
)

jira_metadata_get_schema = extend_schema(
    tags=[JIRA_METADATA_TAG],
    operation_id="jira_metadata_get",
    summary="Get cached Jira project metadata",
    description=(
        "Returns cached metadata for the connection's Jira project. "
        "Any workspace member can read. Response includes `is_stale` "
        "computed from `fetched_at` + `ttl_seconds`."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    responses={
        200: OpenApiResponse(
            response=JiraProjectMetadataSerializer,
            examples=[metadata_fresh_example, metadata_pending_example],
        ),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

jira_metadata_sync_schema = extend_schema(
    tags=[JIRA_METADATA_TAG],
    operation_id="jira_metadata_sync",
    summary="Start Jira metadata sync",
    description=(
        "Queues background sync of issue types, fields, priorities, statuses, "
        "components, labels, boards and sprints. Requires **admin** or **owner**. "
        "Returns `202 Accepted` with `status=syncing`. Poll GET metadata until "
        "`status` is `fresh` or `failed`."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, CONNECTION_ID_PATH],
    request=None,
    responses={
        202: OpenApiResponse(
            response=JiraMetadataSyncResponseSerializer,
            examples=[metadata_sync_accepted_example],
        ),
        400: API_ERROR_400,
        401: API_ERROR_401,
        403: error_response(403, "Not admin/owner.", examples=[FORBIDDEN_ADMIN_EXAMPLE]),
        404: API_ERROR_404,
        409: error_response(
            409,
            "Sync already running (`SYNC_IN_PROGRESS`).",
            examples=[SYNC_IN_PROGRESS_EXAMPLE],
        ),
    },
)
