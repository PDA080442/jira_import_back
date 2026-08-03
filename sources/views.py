"""Thin DRF views for source file upload and read API."""
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sources.openapi import (
    google_sheet_source_deactivate_schema,
    google_sheet_source_detail_schema,
    google_sheet_source_list_create_schema,
    google_sheet_source_refresh_schema,
    source_file_deactivate_schema,
    source_file_detail_schema,
    source_file_list_create_schema,
    source_file_reparse_schema,
)
from sources.serializers import (
    GoogleSheetRefreshResponseSerializer,
    GoogleSheetSourceCreateSerializer,
    GoogleSheetSourceListItemSerializer,
    GoogleSheetSourceSerializer,
    SourceFileListItemSerializer,
    SourceFileReparseResponseSerializer,
    SourceFileSerializer,
    SourceFileUploadSerializer,
)
from sources.services import access as access_service
from sources.services import files as files_service
from sources.services import google_sheets as google_sheets_service


@extend_schema_view(
    get=source_file_list_create_schema["get"],
    post=source_file_list_create_schema["post"],
)
class SourceFileListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, workspace_id):
        sources = files_service.list_source_files(
            workspace_id=workspace_id,
            user=request.user,
        )
        return Response(SourceFileListItemSerializer(sources, many=True).data)

    def post(self, request, workspace_id):
        serializer = SourceFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        source = files_service.create_source_file(
            workspace_id=workspace_id,
            user=request.user,
            upload=data["file"],
            name=data.get("name") or None,
        )
        return Response(
            SourceFileSerializer(source).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(get=source_file_detail_schema)
class SourceFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, pk):
        source = access_service.get_source_file(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        return Response(SourceFileSerializer(source).data)


@extend_schema_view(post=source_file_deactivate_schema)
class SourceFileDeactivateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SourceFileSerializer

    def post(self, request, workspace_id, pk):
        source = access_service.get_source_file(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        source = files_service.deactivate_source_file(source=source, user=request.user)
        return Response(SourceFileSerializer(source).data)


@extend_schema_view(post=source_file_reparse_schema)
class SourceFileReparseView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SourceFileReparseResponseSerializer

    def post(self, request, workspace_id, pk):
        source = access_service.get_source_file(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        result = files_service.start_reparse(source=source, user=request.user)
        return Response(
            SourceFileReparseResponseSerializer(result).data,
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema_view(
    get=google_sheet_source_list_create_schema["get"],
    post=google_sheet_source_list_create_schema["post"],
)
class GoogleSheetSourceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        sources = google_sheets_service.list_google_sources(
            workspace_id=workspace_id,
            user=request.user,
        )
        return Response(GoogleSheetSourceListItemSerializer(sources, many=True).data)

    def post(self, request, workspace_id):
        serializer = GoogleSheetSourceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        source = google_sheets_service.create_google_source(
            workspace_id=workspace_id,
            user=request.user,
            spreadsheet_url=data["spreadsheet_url"],
            name=data.get("name") or None,
            worksheet_title=data.get("worksheet_title") or "",
        )
        return Response(
            GoogleSheetSourceSerializer(source).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(get=google_sheet_source_detail_schema)
class GoogleSheetSourceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, pk):
        source = access_service.get_google_source(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        return Response(GoogleSheetSourceSerializer(source).data)


@extend_schema_view(post=google_sheet_source_deactivate_schema)
class GoogleSheetSourceDeactivateView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GoogleSheetSourceSerializer

    def post(self, request, workspace_id, pk):
        source = access_service.get_google_source(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        source = google_sheets_service.deactivate_google_source(source=source, user=request.user)
        return Response(GoogleSheetSourceSerializer(source).data)


@extend_schema_view(post=google_sheet_source_refresh_schema)
class GoogleSheetSourceRefreshView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GoogleSheetRefreshResponseSerializer

    def post(self, request, workspace_id, pk):
        source = access_service.get_google_source(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        result = google_sheets_service.start_snapshot_refresh(source=source, user=request.user)
        return Response(
            GoogleSheetRefreshResponseSerializer(result).data,
            status=status.HTTP_202_ACCEPTED,
        )
