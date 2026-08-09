"""Serializers for source file upload and read API."""
import os

from rest_framework import serializers

from sources.constants import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    CSV_DELIMITER_CHOICES,
    PRESET_FILE_ONLY_KEYS,
    PRESET_MAX_NAME_LEN,
    SUPPORTED_ENCODINGS,
    extract_spreadsheet_id,
    get_max_file_size_bytes,
    is_supported_encoding,
    normalize_encoding_name,
)
from sources.models import (
    GoogleSheetSource,
    GoogleSheetTab,
    PresetBinding,
    PresetSourceType,
    SourceFile,
    SourcePreset,
    SourceRefreshRun,
    SourceSheet,
    SourceSnapshot,
)
from sources.services import presets as presets_service


class PresetSettingsSerializer(serializers.Serializer):
    sheet = serializers.JSONField(required=False, allow_null=True)
    header_row = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    delimiter = serializers.ChoiceField(
        choices=list(CSV_DELIMITER_CHOICES.keys()),
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    encoding = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)
    selected_columns = serializers.ListField(
        child=serializers.CharField(max_length=255),
        required=False,
        allow_empty=True,
    )
    ignore_rows = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        required=False,
        allow_empty=True,
    )
    preview_rows = serializers.IntegerField(required=False, min_value=1, allow_null=True)

    def validate_encoding(self, value):
        if not value:
            return value
        normalized = normalize_encoding_name(value)
        if not is_supported_encoding(normalized):
            raise serializers.ValidationError(
                f"Supported encodings: {', '.join(sorted(SUPPORTED_ENCODINGS))}.",
            )
        return normalized

    def validate_sheet(self, value):
        if value is None:
            return value
        if isinstance(value, (str, int)):
            return value
        raise serializers.ValidationError("Sheet must be a string name or integer index.")

    def validate(self, attrs):
        source_type = self.context.get("source_type")
        if not source_type:
            return attrs
        for key in PRESET_FILE_ONLY_KEYS:
            if key in attrs and attrs[key] and source_type == PresetSourceType.GOOGLE:
                raise serializers.ValidationError(
                    {key: [f"'{key}' is only allowed for file presets."]},
                )
        return attrs


class SourcePresetCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=PRESET_MAX_NAME_LEN)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    source_type = serializers.ChoiceField(choices=PresetSourceType.choices)
    settings = PresetSettingsSerializer(required=False, default=dict)

    def validate_settings(self, value):
        if value is None:
            return {}
        nested = PresetSettingsSerializer(
            data=value,
            context={"source_type": self.initial_data.get("source_type")},
        )
        nested.is_valid(raise_exception=True)
        return nested.validated_data


class SourcePresetUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=PRESET_MAX_NAME_LEN, required=False)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    settings = PresetSettingsSerializer(required=False)

    def validate_settings(self, value):
        if value is None:
            return value
        source_type = self.context.get("source_type")
        nested = PresetSettingsSerializer(data=value, context={"source_type": source_type})
        nested.is_valid(raise_exception=True)
        return nested.validated_data


class SourcePresetListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourcePreset
        fields = (
            "id",
            "name",
            "description",
            "source_type",
            "version",
            "last_applied_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SourcePresetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourcePreset
        fields = (
            "id",
            "name",
            "description",
            "source_type",
            "settings",
            "version",
            "last_applied_at",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AppliedPresetSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SourcePreset
        fields = ("id", "name", "source_type", "version")
        read_only_fields = fields


class ActiveSnapshotSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSnapshot
        fields = (
            "id",
            "row_count",
            "sheet_count",
            "checksum",
            "is_active",
            "is_truncated",
            "created_at",
        )
        read_only_fields = fields


class SourceSnapshotListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSnapshot
        fields = (
            "id",
            "source_type",
            "source_id",
            "row_count",
            "sheet_count",
            "checksum",
            "is_active",
            "is_truncated",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SourceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceSnapshot
        fields = (
            "id",
            "source_type",
            "source_id",
            "data",
            "row_count",
            "sheet_count",
            "checksum",
            "is_active",
            "is_truncated",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class SourceRefreshRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceRefreshRun
        fields = (
            "id",
            "source_type",
            "source_id",
            "snapshot",
            "trigger",
            "status",
            "from_where",
            "error_message",
            "started_at",
            "finished_at",
            "meta",
            "created_at",
        )
        read_only_fields = fields


class SnapshotCompareQuerySerializer(serializers.Serializer):
    current = serializers.UUIDField(required=False)
    previous = serializers.UUIDField(required=False)


class PresetBindingSerializer(serializers.ModelSerializer):
    preset = SourcePresetListItemSerializer(read_only=True)
    is_stale = serializers.SerializerMethodField()

    class Meta:
        model = PresetBinding
        fields = (
            "id",
            "preset",
            "source_type",
            "source_id",
            "applied_version",
            "status",
            "applied_settings",
            "last_applied_at",
            "last_error",
            "is_stale",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_is_stale(self, obj) -> bool:
        return presets_service.binding_is_stale(obj)


class ApplyPresetRequestSerializer(serializers.Serializer):
    preset_id = serializers.UUIDField()


class SourceFileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delimiter = serializers.ChoiceField(
        choices=list(CSV_DELIMITER_CHOICES.keys()),
        required=False,
        allow_blank=True,
    )
    encoding = serializers.CharField(max_length=32, required=False, allow_blank=True)
    preset_id = serializers.UUIDField(required=False, allow_null=True)

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
    applied_preset = AppliedPresetSummarySerializer(read_only=True)
    active_snapshot = ActiveSnapshotSummarySerializer(read_only=True)

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
            "applied_preset",
            "applied_settings",
            "active_snapshot",
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
    applied_preset = AppliedPresetSummarySerializer(read_only=True)
    active_snapshot = ActiveSnapshotSummarySerializer(read_only=True)

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
            "applied_preset",
            "applied_settings",
            "active_snapshot",
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
    preset_id = serializers.UUIDField(required=False, allow_null=True)

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
    applied_preset = AppliedPresetSummarySerializer(read_only=True)
    active_snapshot = ActiveSnapshotSummarySerializer(read_only=True)

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
            "applied_preset",
            "applied_settings",
            "active_snapshot",
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
    applied_preset = AppliedPresetSummarySerializer(read_only=True)
    active_snapshot = ActiveSnapshotSummarySerializer(read_only=True)

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
            "applied_preset",
            "applied_settings",
            "active_snapshot",
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
