"""Serializers for source file upload and read API."""
import os

from rest_framework import serializers

from sources.constants import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    CSV_DELIMITER_CHOICES,
    SUPPORTED_ENCODINGS,
    extract_spreadsheet_id,
    get_max_file_size_bytes,
    is_supported_encoding,
    normalize_encoding_name,
)
from sources.models import GoogleSheetSource, GoogleSheetTab, SourceFile, SourceSheet


class SourceFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delimiter = serializers.ChoiceField(
        choices=list(CSV_DELIMITER_CHOICES.keys()),
        required=False,
        allow_blank=True,
    )
    encoding = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_encoding(self, value):
        if not value:
            return value
        normalized = normalize_encoding_name(value)
        if not is_supported_encoding(normalized):
            raise serializers.ValidationError(
                f"Supported encodings: {', '.join(sorted(SUPPORTED_ENCODINGS))}.",
            )
        return normalized

    def validate_file(self, upload):
        filename = upload.name or ""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
            )

        max_size = get_max_file_size_bytes()
        if upload.size > max_size:
            raise serializers.ValidationError(f"Maximum file size is {max_size} bytes.")

        content_type = getattr(upload, "content_type", "") or ""
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(f"Unsupported content type: {content_type}.")

        return upload


class SourceFileReparseRequestSerializer(serializers.Serializer):
    delimiter = serializers.ChoiceField(
        choices=list(CSV_DELIMITER_CHOICES.keys()),
        required=False,
        allow_blank=True,
    )
    encoding = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate_encoding(self, value):
        if not value:
            return value
        normalized = normalize_encoding_name(value)
        if not is_supported_encoding(normalized):
            raise serializers.ValidationError(
                f"Supported encodings: {', '.join(sorted(SUPPORTED_ENCODINGS))}.",
            )
        return normalized


class SourceSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSheet
        fields = (
            "id",
            "index",
            "name",
            "row_count",
            "column_count",
            "columns",
            "preview_rows",
        )
        read_only_fields = fields


class SourceFileListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceFile
        fields = (
            "id",
            "name",
            "file_type",
            "size_bytes",
            "content_type",
            "status",
            "sheet_count",
            "encoding",
            "delimiter",
            "encoding_override",
            "delimiter_override",
            "encoding_confidence",
            "warnings",
            "error_message",
            "parse_started_at",
            "parsed_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SourceFileSerializer(serializers.ModelSerializer):
    sheets = SourceSheetSerializer(many=True, read_only=True)

    class Meta:
        model = SourceFile
        fields = (
            "id",
            "name",
            "file_type",
            "size_bytes",
            "content_type",
            "checksum",
            "status",
            "encoding",
            "delimiter",
            "encoding_override",
            "delimiter_override",
            "encoding_confidence",
            "warnings",
            "sheet_count",
            "error_message",
            "parse_started_at",
            "parsed_at",
            "is_active",
            "created_at",
            "updated_at",
            "sheets",
        )
        read_only_fields = fields


class SourceFileReparseResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()


class GoogleSheetSourceCreateSerializer(serializers.Serializer):
    spreadsheet_url = serializers.CharField(max_length=512)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    worksheet_title = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_spreadsheet_url(self, value):
        spreadsheet_id = extract_spreadsheet_id(value)
        if not spreadsheet_id:
            raise serializers.ValidationError(
                "Invalid Google Sheets URL or spreadsheet ID.",
            )
        return value


class GoogleSheetTabSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleSheetTab
        fields = (
            "id",
            "index",
            "name",
            "row_count",
            "column_count",
            "columns",
            "preview_rows",
        )
        read_only_fields = fields


class GoogleSheetSourceListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoogleSheetSource
        fields = (
            "id",
            "name",
            "spreadsheet_id",
            "spreadsheet_url",
            "worksheet_title",
            "status",
            "sheet_count",
            "error_message",
            "last_sync_started_at",
            "synced_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class GoogleSheetSourceSerializer(serializers.ModelSerializer):
    tabs = GoogleSheetTabSerializer(many=True, read_only=True)

    class Meta:
        model = GoogleSheetSource
        fields = (
            "id",
            "name",
            "spreadsheet_id",
            "spreadsheet_url",
            "worksheet_title",
            "status",
            "sheet_count",
            "error_message",
            "last_sync_started_at",
            "synced_at",
            "is_active",
            "created_at",
            "updated_at",
            "tabs",
        )
        read_only_fields = fields


class GoogleSheetRefreshResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detail = serializers.CharField()
