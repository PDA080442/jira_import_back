"""ORM models for uploaded Excel/CSV source files."""
import uuid

from django.conf import settings as django_settings
from django.db import models


def source_file_upload_path(instance, filename: str) -> str:
    return f"sources/{instance.workspace_id}/{instance.id}/{filename}"


class SourceFileType(models.TextChoices):
    XLSX = "xlsx", "Excel (.xlsx)"
    CSV = "csv", "CSV"


class SourceParseStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PARSING = "parsing", "Parsing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class PresetSourceType(models.TextChoices):
    FILE = "file", "File (Excel/CSV)"
    GOOGLE = "google", "Google Sheets"


class PresetBindingStatus(models.TextChoices):
    APPLIED = "applied", "Applied"
    FAILED = "failed", "Failed"
    STALE = "stale", "Stale"


class SourcePreset(models.Model):
    """Named reusable configuration for a source type within a workspace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "tenants.Workspace",
        on_delete=models.CASCADE,
        related_name="source_presets",
    )
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=2000, blank=True, default="")
    source_type = models.CharField(max_length=16, choices=PresetSourceType.choices)
    settings = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    last_applied_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_source_presets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
            models.Index(fields=["workspace", "source_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "source_type", "name"],
                condition=models.Q(is_active=True),
                name="unique_active_source_preset_name_per_workspace_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.source_type})"


class PresetBinding(models.Model):
    """Links a preset to a concrete source instance with apply history."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "tenants.Workspace",
        on_delete=models.CASCADE,
        related_name="preset_bindings",
    )
    preset = models.ForeignKey(
        SourcePreset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bindings",
    )
    source_type = models.CharField(max_length=16, choices=PresetSourceType.choices)
    source_id = models.UUIDField()
    applied_version = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=16,
        choices=PresetBindingStatus.choices,
        default=PresetBindingStatus.APPLIED,
    )
    applied_settings = models.JSONField(default=dict, blank=True)
    last_applied_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=2000, blank=True, default="")
    applied_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preset_bindings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_applied_at", "-updated_at"]
        indexes = [
            models.Index(fields=["workspace", "preset"]),
            models.Index(fields=["workspace", "last_applied_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id"],
                name="unique_preset_binding_per_source",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id} -> preset {self.preset_id}"


class SourceFile(models.Model):
    """Workspace-scoped uploaded Excel/CSV file."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "tenants.Workspace",
        on_delete=models.CASCADE,
        related_name="source_files",
    )
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to=source_file_upload_path)
    file_type = models.CharField(max_length=8, choices=SourceFileType.choices)
    size_bytes = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=128, blank=True, default="")
    checksum = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=SourceParseStatus.choices,
        default=SourceParseStatus.PENDING,
    )
    encoding = models.CharField(max_length=32, blank=True, default="")
    delimiter = models.CharField(max_length=8, blank=True, default="")
    encoding_override = models.CharField(max_length=32, blank=True, default="")
    delimiter_override = models.CharField(max_length=8, blank=True, default="")
    encoding_confidence = models.FloatField(null=True, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    applied_preset = models.ForeignKey(
        SourcePreset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_source_files",
    )
    applied_settings = models.JSONField(default=dict, blank=True)
    sheet_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=2000, blank=True, default="")
    parse_started_at = models.DateTimeField(null=True, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_source_files",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.file_type})"


class SourceSheet(models.Model):
    """Parsed sheet/tab from a source file (Excel sheet or CSV tab)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_file = models.ForeignKey(
        SourceFile,
        on_delete=models.CASCADE,
        related_name="sheets",
    )
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    row_count = models.PositiveIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)
    columns = models.JSONField(default=list, blank=True)
    preview_rows = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["index"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_file", "index"],
                name="unique_source_sheet_index_per_file",
            ),
        ]
        indexes = [
            models.Index(fields=["source_file"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} (#{self.index})"


class GoogleSheetSource(models.Model):
    """Workspace-scoped Google Sheets source (no per-source credentials)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "tenants.Workspace",
        on_delete=models.CASCADE,
        related_name="google_sheet_sources",
    )
    name = models.CharField(max_length=255)
    spreadsheet_id = models.CharField(max_length=128)
    spreadsheet_url = models.URLField(max_length=512, blank=True, default="")
    worksheet_title = models.CharField(max_length=255, blank=True, default="")
    applied_preset = models.ForeignKey(
        SourcePreset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_google_sources",
    )
    applied_settings = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=SourceParseStatus.choices,
        default=SourceParseStatus.PENDING,
    )
    sheet_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=2000, blank=True, default="")
    last_sync_started_at = models.DateTimeField(null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_google_sheet_sources",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
            models.Index(fields=["workspace", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.spreadsheet_id})"


class GoogleSheetTab(models.Model):
    """Cached tab/sheet from a Google Sheets source."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        GoogleSheetSource,
        on_delete=models.CASCADE,
        related_name="tabs",
    )
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    row_count = models.PositiveIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)
    columns = models.JSONField(default=list, blank=True)
    preview_rows = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["index"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "index"],
                name="unique_google_sheet_tab_index_per_source",
            ),
        ]
        indexes = [
            models.Index(fields=["source"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} (#{self.index})"
