"""Thin DRF views: validate input, delegate to services.

Access control (member/admin/owner) is enforced in services — not in permission classes —
so non-members receive 404 instead of 403.
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tenants.serializers import (
    WorkspaceCreateSerializer,
    WorkspaceInviteAcceptSerializer,
    WorkspaceInviteCreateSerializer,
    WorkspaceInviteResponseSerializer,
    WorkspaceMemberSerializer,
    WorkspaceSerializer,
    WorkspaceUpdateSerializer,
)
from tenants.services import invite as invite_service
from tenants.services import membership as membership_service
from tenants.services import workspace as workspace_service


class WorkspaceListCreateView(APIView):
    """GET/POST /api/workspaces/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        workspaces = workspace_service.list_workspaces(user=request.user)
        return Response(WorkspaceSerializer(workspaces, many=True).data)

    def post(self, request):
        serializer = WorkspaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = workspace_service.create_workspace(
            user=request.user,
            name=serializer.validated_data["name"],
        )
        return Response(WorkspaceSerializer(workspace).data, status=status.HTTP_201_CREATED)


class WorkspaceDetailView(APIView):
    """GET/PATCH/DELETE /api/workspaces/{pk}/ — access checks in services (404/403)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        workspace = workspace_service.get_workspace(workspace_id=pk, user=request.user)
        return Response(WorkspaceSerializer(workspace).data)

    def patch(self, request, pk):
        workspace = workspace_service.get_workspace(workspace_id=pk, user=request.user)
        serializer = WorkspaceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        workspace = workspace_service.update_workspace(
            workspace=workspace,
            user=request.user,
            name=serializer.validated_data["name"],
        )
        return Response(WorkspaceSerializer(workspace).data)

    def delete(self, request, pk):
        workspace = workspace_service.get_workspace(workspace_id=pk, user=request.user)
        workspace_service.delete_workspace(workspace=workspace, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceMemberListView(APIView):
    """GET /api/workspaces/{pk}/members/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        workspace = workspace_service.get_workspace(workspace_id=pk, user=request.user)
        members = membership_service.list_members(workspace=workspace)
        return Response(
            {"members": WorkspaceMemberSerializer(members, many=True).data},
        )


class WorkspaceInviteCreateView(APIView):
    """POST /api/workspaces/{pk}/invites/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        workspace = workspace_service.get_workspace(workspace_id=pk, user=request.user)
        serializer = WorkspaceInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = invite_service.create_invite(
            workspace=workspace,
            user=request.user,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
        )
        return Response(
            WorkspaceInviteResponseSerializer(invite).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceInviteAcceptView(APIView):
    """POST /api/workspaces/invites/accept/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WorkspaceInviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        membership = invite_service.accept_invite(
            user=request.user,
            raw_token=serializer.validated_data["token"],
        )
        return Response(
            {
                "message": "Invite accepted.",
                "workspace_id": str(membership.workspace_id),
                "role": membership.role,
            },
        )
