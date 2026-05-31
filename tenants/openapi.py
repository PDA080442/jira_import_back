"""OpenAPI schema helpers for workspace-membership endpoints."""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers

from core.openapi import (
    API_ERROR_400,
    API_ERROR_401,
    API_ERROR_403,
    API_ERROR_404,
    TRACE_ID_HEADER,
    WORKSPACE_ID_PATH,
    error_response,
)
from tenants.serializers import (
    WorkspaceCreateSerializer,
    WorkspaceInviteAcceptSerializer,
    WorkspaceInviteCreateSerializer,
    WorkspaceInviteResponseSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
    WorkspaceUpdateSerializer,
)

WORKSPACE_TAG = "Workspaces"

WorkspaceMemberListResponseSerializer = inline_serializer(
    name="WorkspaceMemberListResponse",
    fields={
        "members": WorkspaceMemberSerializer(many=True),
    },
)

InviteAcceptResponseSerializer = inline_serializer(
    name="WorkspaceInviteAcceptResponse",
    fields={
        "message": serializers.CharField(help_text="Success message."),
        "workspace_id": serializers.UUIDField(help_text="Workspace the user joined."),
        "role": serializers.ChoiceField(
            choices=["owner", "admin", "editor", "viewer"],
            help_text="Assigned membership role.",
        ),
    },
)

FORBIDDEN_ADMIN_EXAMPLE = OpenApiExample(
    name="Not admin",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "FORBIDDEN",
        "message": "Only workspace admins can update the workspace.",
        "fieldErrors": {},
    },
    response_only=True,
)

FORBIDDEN_OWNER_EXAMPLE = OpenApiExample(
    name="Not owner",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "FORBIDDEN",
        "message": "Only the workspace owner can delete the workspace.",
        "fieldErrors": {},
    },
    response_only=True,
)

INVITE_TOKEN_INVALID_EXAMPLE = OpenApiExample(
    name="Invalid invite token",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "TOKEN_INVALID",
        "message": "Invalid invite token.",
        "fieldErrors": {},
    },
    response_only=True,
)

workspace_example = OpenApiExample(
    name="Workspace",
    value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "My Team",
        "slug": "my-team",
        "owner_id": "660e8400-e29b-41d4-a716-446655440001",
        "created_at": "2026-05-31T12:00:00.000000Z",
        "updated_at": "2026-05-31T12:00:00.000000Z",
    },
    response_only=True,
)

workspace_list_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_list",
    summary="List my workspaces",
    description=(
        "Returns all workspaces where the authenticated user has an active membership. "
        "Ordered by `created_at` descending."
    ),
    parameters=[TRACE_ID_HEADER],
    responses={
        200: OpenApiResponse(
            response=WorkspaceSerializer(many=True),
            description="List of workspaces.",
            examples=[workspace_example],
        ),
        401: API_ERROR_401,
    },
)

workspace_create_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_create",
    summary="Create workspace",
    description=(
        "Creates a workspace and assigns the caller as **owner**. "
        "Slug is generated automatically from the name and is immutable."
    ),
    parameters=[TRACE_ID_HEADER],
    request=WorkspaceCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=WorkspaceSerializer,
            description="Created workspace.",
            examples=[workspace_example],
        ),
        400: API_ERROR_400,
        401: API_ERROR_401,
    },
    examples=[
        OpenApiExample(name="Create", value={"name": "My Team"}, request_only=True),
    ],
)

workspace_get_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_get",
    summary="Get workspace by id",
    description=(
        "Returns workspace details for members only. "
        "**Non-members receive 404 NOT_FOUND** (not 403) to avoid leaking workspace existence."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    responses={
        200: OpenApiResponse(
            response=WorkspaceSerializer,
            examples=[workspace_example],
        ),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

workspace_update_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_update",
    summary="Update workspace name",
    description="Requires **admin** or **owner** role. Slug cannot be changed via API.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    request=WorkspaceUpdateSerializer,
    responses={
        200: OpenApiResponse(response=WorkspaceSerializer, examples=[workspace_example]),
        400: API_ERROR_400,
        401: API_ERROR_401,
        403: error_response(
            403,
            "Caller is member but not admin/owner.",
            examples=[FORBIDDEN_ADMIN_EXAMPLE],
        ),
        404: API_ERROR_404,
    },
)

workspace_delete_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_delete",
    summary="Delete workspace",
    description=(
        "Permanently deletes the workspace and all memberships. "
        "Requires **owner** role only. Pending invites are invalidated."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    responses={
        204: OpenApiResponse(description="Workspace deleted."),
        401: API_ERROR_401,
        403: error_response(
            403,
            "Only owner can delete.",
            examples=[FORBIDDEN_OWNER_EXAMPLE],
        ),
        404: API_ERROR_404,
    },
)

workspace_members_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_members_list",
    summary="List workspace members",
    description="Returns all active members with role and join date. Any member can read.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    responses={
        200: OpenApiResponse(
            response=WorkspaceMemberListResponseSerializer,
            description="Member list wrapper.",
            examples=[
                OpenApiExample(
                    name="Members",
                    value={
                        "members": [
                            {
                                "id": "770e8400-e29b-41d4-a716-446655440002",
                                "user_id": "660e8400-e29b-41d4-a716-446655440001",
                                "email": "owner@example.com",
                                "role": "owner",
                                "joined_at": "2026-05-31T12:00:00.000000Z",
                            },
                        ],
                    },
                    response_only=True,
                ),
            ],
        ),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

workspace_invite_create_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_invite_create",
    summary="Invite user by email",
    description=(
        "Creates a pending invite and queues invitation email (Celery). "
        "Requires **admin** or **owner**. Role must be `admin`, `editor`, or `viewer` — **not `owner`**. "
        "Duplicate active members and pending invites for the same email are rejected."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
    request=WorkspaceInviteCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=WorkspaceInviteResponseSerializer,
            description="Created invite (token is sent by email, not returned in API).",
            examples=[
                OpenApiExample(
                    name="Invite",
                    value={
                        "id": "880e8400-e29b-41d4-a716-446655440003",
                        "email": "colleague@example.com",
                        "role": "editor",
                        "expires_at": "2026-06-07T12:00:00.000000Z",
                    },
                    response_only=True,
                ),
            ],
        ),
        400: API_ERROR_400,
        401: API_ERROR_401,
        403: error_response(
            403,
            "Caller is member but not admin/owner.",
            examples=[FORBIDDEN_ADMIN_EXAMPLE],
        ),
        404: API_ERROR_404,
    },
    examples=[
        OpenApiExample(
            name="Invite editor",
            value={"email": "colleague@example.com", "role": "editor"},
            request_only=True,
        ),
    ],
)

workspace_invite_accept_schema = extend_schema(
    tags=[WORKSPACE_TAG],
    operation_id="workspace_invite_accept",
    summary="Accept workspace invite",
    description=(
        "Accepts invite using token from email. "
        "Authenticated user's email **must match** invite email. "
        "Creates membership and invalidates the invite token."
    ),
    parameters=[TRACE_ID_HEADER],
    request=WorkspaceInviteAcceptSerializer,
    responses={
        200: OpenApiResponse(
            response=InviteAcceptResponseSerializer,
            description="Membership created.",
            examples=[
                OpenApiExample(
                    name="Accepted",
                    value={
                        "message": "Invite accepted.",
                        "workspace_id": "550e8400-e29b-41d4-a716-446655440000",
                        "role": "editor",
                    },
                    response_only=True,
                ),
            ],
        ),
        400: error_response(
            400,
            "Invalid/expired token or duplicate member.",
            examples=[INVITE_TOKEN_INVALID_EXAMPLE],
        ),
        401: API_ERROR_401,
        403: error_response(
            403,
            "Invite email does not match authenticated user.",
            examples=[FORBIDDEN_ADMIN_EXAMPLE],
        ),
    },
)
