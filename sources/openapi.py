"""OpenAPI schema helpers for source file endpoints."""
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema

from core.openapi import (
    API_ERROR_400,
    API_ERROR_401,
    API_ERROR_403,
    API_ERROR_404,
    TRACE_ID_HEADER,
    error_response,
)
from sources.serializers import (
    SourceFileListItemSerializer,
    SourceFileReparseResponseSerializer,
    SourceFileSerializer,
    SourceFileUploadSerializer,
)

SOURCE_FILES_TAG = "Source Files"

WORKSPACE_ID_PATH = OpenApiParameter(
    name="workspace_id",
    type=str,
    location=OpenApiParameter.PATH,
    description="Workspace UUID.",
)

SOURCE_ID_PATH = OpenApiParameter(
    name="pk",
    type=str,
    location=OpenApiParameter.PATH,
    description="Source file UUID.",
)

PARSE_IN_PROGRESS_EXAMPLE = OpenApiExample(
    name="Parse in progress",
    value={
        "traceId": "550e8400-e29b-41d4-a716-446655440000",
        "code": "PARSE_IN_PROGRESS",
        "message": "Source file parsing is already in progress.",
        "fieldErrors": {},
    },
    response_only=True,
)

source_pending_example = OpenApiExample(
    name="Uploaded, pending parse",
    value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "backlog",
        "file_type": "xlsx",
        "size_bytes": 12345,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "checksum": "abc123",
        "status": "pending",
        "encoding": "",
        "delimiter": "",
        "sheet_count": 0,
        "error_message": "",
        "parse_started_at": None,
        "parsed_at": None,
        "is_active": True,
        "created_at": "2026-08-03T12:00:00.000000Z",
        "updated_at": "2026-08-03T12:00:00.000000Z",
        "sheets": [],
    },
    response_only=True,
)

source_ready_example = OpenApiExample(
    name="Parsed and ready",
    value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "backlog",
        "file_type": "csv",
        "size_bytes": 2048,
        "content_type": "text/csv",
        "checksum": "def456",
        "status": "ready",
        "encoding": "utf-8",
        "delimiter": ",",
        "sheet_count": 1,
        "error_message": "",
        "parse_started_at": "2026-08-03T12:00:01.000000Z",
        "parsed_at": "2026-08-03T12:00:02.000000Z",
        "is_active": True,
        "created_at": "2026-08-03T12:00:00.000000Z",
        "updated_at": "2026-08-03T12:00:02.000000Z",
        "sheets": [
            {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "index": 0,
                "name": "backlog",
                "row_count": 101,
                "column_count": 3,
                "columns": [
                    {"index": 0, "name": "Summary"},
                    {"index": 1, "name": "Priority"},
                    {"index": 2, "name": "Assignee"},
                ],
                "preview_rows": [
                    ["Fix login", "High", "alex"],
                    ["Add export", "Medium", "maria"],
                ],
            },
        ],
    },
    response_only=True,
)

source_failed_example = OpenApiExample(
    name="Parse failed",
    value={
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "broken",
        "file_type": "xlsx",
        "size_bytes": 512,
        "content_type": "application/octet-stream",
        "checksum": "ghi789",
        "status": "failed",
        "encoding": "",
        "delimiter": "",
        "sheet_count": 0,
        "error_message": "Excel file contains no worksheets.",
        "parse_started_at": "2026-08-03T12:00:01.000000Z",
        "parsed_at": None,
        "is_active": True,
        "created_at": "2026-08-03T12:00:00.000000Z",
        "updated_at": "2026-08-03T12:00:02.000000Z",
        "sheets": [],
    },
    response_only=True,
)

source_reparse_accepted_example = OpenApiExample(
    name="Reparse accepted",
    value={"status": "pending", "detail": "Source file parsing started."},
    response_only=True,
)

source_file_list_create_schema = {
    "get": extend_schema(
        tags=[SOURCE_FILES_TAG],
        operation_id="source_file_list",
        summary="List source files",
        description="Returns active source files in the workspace. Any workspace member can read.",
        parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
        responses={
            200: OpenApiResponse(response=SourceFileListItemSerializer(many=True)),
            401: API_ERROR_401,
            404: API_ERROR_404,
        },
    ),
    "post": extend_schema(
        tags=[SOURCE_FILES_TAG],
        operation_id="source_file_upload",
        summary="Upload Excel/CSV source file",
        description=(
            "Uploads `.xlsx` or `.csv` file. Parsing runs asynchronously in Celery. "
            "Requires editor, admin, or owner role."
        ),
        parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH],
        request={
            "multipart/form-data": SourceFileUploadSerializer,
        },
        responses={
            201: OpenApiResponse(response=SourceFileSerializer, examples=[source_pending_example]),
            400: API_ERROR_400,
            401: API_ERROR_401,
            403: API_ERROR_403,
            404: API_ERROR_404,
        },
    ),
}

source_file_detail_schema = extend_schema(
    tags=[SOURCE_FILES_TAG],
    operation_id="source_file_get",
    summary="Get source file with sheets",
    description=(
        "Returns source file details including parsed sheets, columns, and preview rows "
        "when status is `ready`."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, SOURCE_ID_PATH],
    responses={
        200: OpenApiResponse(
            response=SourceFileSerializer,
            examples=[source_ready_example, source_pending_example, source_failed_example],
        ),
        401: API_ERROR_401,
        404: API_ERROR_404,
    },
)

source_file_deactivate_schema = extend_schema(
    tags=[SOURCE_FILES_TAG],
    operation_id="source_file_deactivate",
    summary="Deactivate source file (soft delete)",
    description="Marks source file as inactive. Requires editor, admin, or owner role.",
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, SOURCE_ID_PATH],
    request=None,
    responses={
        200: OpenApiResponse(response=SourceFileSerializer),
        401: API_ERROR_401,
        403: API_ERROR_403,
        404: API_ERROR_404,
    },
)

source_file_reparse_schema = extend_schema(
    tags=[SOURCE_FILES_TAG],
    operation_id="source_file_reparse",
    summary="Re-run source file parsing",
    description=(
        "Triggers background re-parse of the uploaded file. "
        "Returns 409 if parsing is already in progress."
    ),
    parameters=[TRACE_ID_HEADER, WORKSPACE_ID_PATH, SOURCE_ID_PATH],
    request=None,
    responses={
        202: OpenApiResponse(
            response=SourceFileReparseResponseSerializer,
            examples=[source_reparse_accepted_example],
        ),
        401: API_ERROR_401,
        403: API_ERROR_403,
        404: API_ERROR_404,
        409: error_response(
            409,
            "Parse already in progress.",
            examples=[PARSE_IN_PROGRESS_EXAMPLE],
        ),
    },
)
