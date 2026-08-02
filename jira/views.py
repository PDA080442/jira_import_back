"""Thin DRF views: validate input, delegate to services.

Access control is enforced in jira.services — non-members get 404, non-admin mutations get 403.
"""
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from jira.openapi import (
    jira_connection_create_schema,
    jira_connection_deactivate_schema,
    jira_connection_get_schema,
    jira_connection_list_schema,
    jira_connection_test_schema,
    jira_connection_update_schema,
    jira_guide_get_schema,
    jira_guide_list_schema,
    jira_metadata_get_schema,
    jira_metadata_sync_schema,
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
from jira.services import connection as connection_service
from jira.services import guide as guide_service
from jira.services import metadata as metadata_service
from jira.services import test as test_service


@extend_schema_view(
    get=jira_connection_list_schema,
    post=jira_connection_create_schema,
)
class JiraConnectionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        connections = connection_service.list_connections(
            workspace_id=workspace_id,
            user=request.user,
        )
        return Response(JiraConnectionSerializer(connections, many=True).data)

    def post(self, request, workspace_id):
        serializer = JiraConnectionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        connection = connection_service.create_connection(
            workspace_id=workspace_id,
            user=request.user,
            name=data["name"],
            base_url=data["base_url"],
            email=data["email"],
            api_token=data["api_token"],
            project_key=data["project_key"],
            board_id=data.get("board_id", ""),
            extra=data.get("extra"),
            is_active=data.get("is_active", True),
        )
        return Response(
            JiraConnectionSerializer(connection).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=jira_connection_get_schema,
    patch=jira_connection_update_schema,
)
class JiraConnectionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, pk):
        connection = connection_service.get_connection(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        return Response(JiraConnectionSerializer(connection).data)

    def patch(self, request, workspace_id, pk):
        connection = connection_service.get_connection(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        serializer = JiraConnectionUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        connection = connection_service.update_connection(
            connection=connection,
            user=request.user,
            **serializer.validated_data,
        )
        return Response(JiraConnectionSerializer(connection).data)


@extend_schema_view(post=jira_connection_deactivate_schema)
class JiraConnectionDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        connection = connection_service.get_connection(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        connection = connection_service.deactivate_connection(
            connection=connection,
            user=request.user,
        )
        return Response(JiraConnectionSerializer(connection).data)


@extend_schema_view(post=jira_connection_test_schema)
class JiraConnectionTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        connection = connection_service.get_connection(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        result = test_service.run_connection_test(connection=connection, user=request.user)
        return Response(JiraConnectionTestResultSerializer(result).data)


@extend_schema_view(get=jira_metadata_get_schema)
class JiraMetadataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, pk):
        metadata = metadata_service.get_metadata(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        return Response(JiraProjectMetadataSerializer(metadata).data)


@extend_schema_view(post=jira_metadata_sync_schema)
class JiraMetadataSyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        result = metadata_service.start_metadata_sync(
            workspace_id=workspace_id,
            connection_id=pk,
            user=request.user,
        )
        return Response(JiraMetadataSyncResponseSerializer(result).data, status=status.HTTP_202_ACCEPTED)


@extend_schema_view(get=jira_guide_list_schema)
class JiraGuideListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        guides = guide_service.list_guides()
        return Response(JiraGuideListItemSerializer(guides, many=True).data)


@extend_schema_view(get=jira_guide_get_schema)
class JiraGuideDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        guide = guide_service.get_guide(slug=slug)
        return Response(JiraGuideSerializer(guide).data)
