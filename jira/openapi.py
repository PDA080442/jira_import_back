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
)

JIRA_CONNECTIONS_TAG = "Jira Connections"

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
