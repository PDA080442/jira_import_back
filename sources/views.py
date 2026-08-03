"""Thin DRF views for source file upload and read API."""
from drf_spectacular.utils import extend_schema_view
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sources.openapi import (
    google_sheet_source_apply_preset_schema,
    google_sheet_source_deactivate_schema,
    google_sheet_source_detail_schema,
    google_sheet_source_list_create_schema,
    google_sheet_source_refresh_schema,
    source_file_apply_preset_schema,
    source_file_deactivate_schema,
    source_file_detail_schema,
    source_file_list_create_schema,
    source_file_reparse_schema,
    source_preset_deactivate_schema,
    source_preset_detail_schema,
    source_preset_list_create_schema,
    source_preset_recent_schema,
)
from sources.models import PresetSourceType
from sources.serializers import (
    ApplyPresetRequestSerializer,
    GoogleSheetRefreshResponseSerializer,
    GoogleSheetSourceCreateSerializer,
    GoogleSheetSourceListItemSerializer,
    GoogleSheetSourceSerializer,
    PresetBindingSerializer,
    SourceFileListItemSerializer,
    SourceFileReparseRequestSerializer,
    SourceFileReparseResponseSerializer,
    SourceFileSerializer,
    SourceFileUploadSerializer,
    SourcePresetCreateSerializer,
    SourcePresetListItemSerializer,
    SourcePresetSerializer,
    SourcePresetUpdateSerializer,
)
from sources.services import access as access_service
from sources.services import files as files_service
from sources.services import google_sheets as google_sheets_service
from sources.services import presets as presets_service


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
            delimiter=data.get("delimiter") or None,
            encoding=data.get("encoding") or None,
            preset_id=data.get("preset_id"),
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
        serializer = SourceFileReparseRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = files_service.start_reparse(
            source=source,
            user=request.user,
            delimiter=data.get("delimiter") if "delimiter" in data else None,
            encoding=data.get("encoding") if "encoding" in data else None,
        )
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
            preset_id=data.get("preset_id"),
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


@extend_schema_view(
    get=source_preset_list_create_schema["get"],
    post=source_preset_list_create_schema["post"],
)
class SourcePresetListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        source_type = request.query_params.get("source_type")
        presets = presets_service.list_presets(
            workspace_id=workspace_id,
            user=request.user,
            source_type=source_type or None,
        )
        return Response(SourcePresetListItemSerializer(presets, many=True).data)

    def post(self, request, workspace_id):
        serializer = SourcePresetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        preset = presets_service.create_preset(
            workspace_id=workspace_id,
            user=request.user,
            name=data["name"],
            source_type=data["source_type"],
            settings=data.get("settings") or {},
            description=data.get("description") or "",
        )
        return Response(
            SourcePresetSerializer(preset).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(get=source_preset_recent_schema)
class RecentConfigsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id):
        limit = int(request.query_params.get("limit", 10))
        bindings = presets_service.list_recent_configs(
            workspace_id=workspace_id,
            user=request.user,
            limit=limit,
        )
        return Response(PresetBindingSerializer(bindings, many=True).data)


@extend_schema_view(
    get=source_preset_detail_schema["get"],
    patch=source_preset_detail_schema["patch"],
)
class SourcePresetDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workspace_id, pk):
        preset = presets_service.get_preset(
            workspace_id=workspace_id,
            preset_id=pk,
            user=request.user,
        )
        return Response(SourcePresetSerializer(preset).data)

    def patch(self, request, workspace_id, pk):
        preset = presets_service.get_preset(
            workspace_id=workspace_id,
            preset_id=pk,
            user=request.user,
        )
        serializer = SourcePresetUpdateSerializer(
            data=request.data,
            partial=True,
            context={"source_type": preset.source_type},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        preset = presets_service.update_preset(
            preset=preset,
            user=request.user,
            name=data.get("name"),
            description=data.get("description"),
            settings=data.get("settings"),
        )
        return Response(SourcePresetSerializer(preset).data)


@extend_schema_view(post=source_preset_deactivate_schema)
class SourcePresetDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        preset = presets_service.get_preset(
            workspace_id=workspace_id,
            preset_id=pk,
            user=request.user,
        )
        preset = presets_service.deactivate_preset(preset=preset, user=request.user)
        return Response(SourcePresetSerializer(preset).data)


@extend_schema_view(post=source_file_apply_preset_schema)
class SourceFileApplyPresetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        source = access_service.get_source_file(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        serializer = ApplyPresetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preset = presets_service.get_preset(
            workspace_id=workspace_id,
            preset_id=serializer.validated_data["preset_id"],
            user=request.user,
        )
        binding = presets_service.apply_preset_to_source(
            preset=preset,
            user=request.user,
            source_type=PresetSourceType.FILE,
            source=source,
        )
        return Response(PresetBindingSerializer(binding).data)


@extend_schema_view(post=google_sheet_source_apply_preset_schema)
class GoogleSheetSourceApplyPresetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workspace_id, pk):
        source = access_service.get_google_source(
            workspace_id=workspace_id,
            source_id=pk,
            user=request.user,
        )
        serializer = ApplyPresetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preset = presets_service.get_preset(
            workspace_id=workspace_id,
            preset_id=serializer.validated_data["preset_id"],
            user=request.user,
        )
        binding = presets_service.apply_preset_to_source(
            preset=preset,
            user=request.user,
            source_type=PresetSourceType.GOOGLE,
            source=source,
        )
        return Response(PresetBindingSerializer(binding).data)
