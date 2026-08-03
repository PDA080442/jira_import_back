"""ORM models for uploaded Excel/CSV source files."""
import uuid

from django.conf import settings
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
    sheet_count = models.PositiveIntegerField(default=0)
    error_message = models.CharField(max_length=2000, blank=True, default="")
    parse_started_at = models.DateTimeField(null=True, blank=True)
    parsed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
