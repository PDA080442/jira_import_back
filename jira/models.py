"""ORM models for Jira Cloud connections and cached project metadata."""
import uuid
from datetime import timedelta

from django.db import models
from django.conf import settings
from django.utils import timezone


class JiraTestStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


class JiraSyncStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SYNCING = "syncing", "Syncing"
    FRESH = "fresh", "Fresh"
    FAILED = "failed", "Failed"


class JiraMetadataItemKind(models.TextChoices):
    PRIORITY = "priority", "Priority"
    STATUS = "status", "Status"
    COMPONENT = "component", "Component"
    LABEL = "label", "Label"


class JiraConnection(models.Model):
    """Workspace-scoped Jira Cloud connection; API token stored encrypted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        "tenants.Workspace",
        on_delete=models.CASCADE,
        related_name="jira_connections",
    )
    name = models.CharField(max_length=255)
    base_url = models.URLField(max_length=512)
    email = models.EmailField()
    api_token_encrypted = models.TextField()
    project_key = models.CharField(max_length=64)
    board_id = models.CharField(max_length=64, blank=True, default="")
    extra = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_status = models.CharField(
        max_length=16,
        choices=JiraTestStatus.choices,
        default=JiraTestStatus.UNKNOWN,
    )
    last_test_error = models.CharField(max_length=512, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jira_connections",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                name="unique_jira_connection_name_per_workspace",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.project_key})"


class JiraProjectMetadata(models.Model):
    """Cached Jira project metadata for a connection."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.OneToOneField(
        JiraConnection,
        on_delete=models.CASCADE,
        related_name="project_metadata",
    )
    project_id = models.CharField(max_length=64, blank=True, default="")
    project_name = models.CharField(max_length=255, blank=True, default="")
    project_key = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=JiraSyncStatus.choices,
        default=JiraSyncStatus.PENDING,
    )
    fetched_at = models.DateTimeField(null=True, blank=True)
    ttl_seconds = models.PositiveIntegerField(default=3600)
    last_sync_started_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=512, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["connection", "status"]),
            models.Index(fields=["fetched_at"]),
        ]

    def __str__(self) -> str:
        return f"Metadata {self.project_key or self.connection.project_key}"

    @property
    def is_stale(self) -> bool:
        if self.fetched_at is None:
            return True
        expires_at = self.fetched_at + timedelta(seconds=self.ttl_seconds)
        return timezone.now() > expires_at


class JiraIssueType(models.Model):
    metadata = models.ForeignKey(
        JiraProjectMetadata,
        on_delete=models.CASCADE,
        related_name="issue_types",
    )
    jira_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    hierarchy_level = models.IntegerField(null=True, blank=True)
    is_subtask = models.BooleanField(default=False)
    description = models.TextField(blank=True, default="")
    icon_url = models.URLField(max_length=512, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["metadata", "jira_id"],
                name="unique_jira_issue_type_per_metadata",
            ),
        ]
        indexes = [
            models.Index(fields=["metadata"]),
        ]

    def __str__(self) -> str:
        return self.name


class JiraField(models.Model):
    metadata = models.ForeignKey(
        JiraProjectMetadata,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    jira_id = models.CharField(max_length=64)
    key = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    is_custom = models.BooleanField(default=False)
    schema_type = models.CharField(max_length=128, blank=True, default="")
    is_required = models.BooleanField(default=False)
    template_field_type = models.CharField(max_length=64, blank=True, default="text")
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["metadata", "key"],
                name="unique_jira_field_key_per_metadata",
            ),
        ]
        indexes = [
            models.Index(fields=["metadata"]),
            models.Index(fields=["metadata", "is_custom"]),
        ]

    def __str__(self) -> str:
        return self.key


class JiraBoard(models.Model):
    metadata = models.ForeignKey(
        JiraProjectMetadata,
        on_delete=models.CASCADE,
        related_name="boards",
    )
    jira_board_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    board_type = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["metadata", "jira_board_id"],
                name="unique_jira_board_per_metadata",
            ),
        ]
        indexes = [
            models.Index(fields=["metadata"]),
        ]

    def __str__(self) -> str:
        return self.name


class JiraSprint(models.Model):
    board = models.ForeignKey(
        JiraBoard,
        on_delete=models.CASCADE,
        related_name="sprints",
    )
    jira_sprint_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    state = models.CharField(max_length=32, blank=True, default="")
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    goal = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["board", "jira_sprint_id"],
                name="unique_jira_sprint_per_board",
            ),
        ]
        indexes = [
            models.Index(fields=["board"]),
        ]

    def __str__(self) -> str:
        return self.name


class JiraGuide(models.Model):
    """Editable help content (e.g. connections page onboarding), fetched by frontend."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=128, unique=True)
    title = models.CharField(max_length=255)
    summary = models.CharField(max_length=512, blank=True, default="")
    locale = models.CharField(max_length=16, default="ru")
    content = models.JSONField(default=list, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        indexes = [
            models.Index(fields=["is_published"]),
        ]

    def __str__(self) -> str:
        return f"{self.slug} ({self.locale})"


class JiraMetadataItem(models.Model):
    """Generic cached item: priority, status, component, label."""

    metadata = models.ForeignKey(
        JiraProjectMetadata,
        on_delete=models.CASCADE,
        related_name="items",
    )
    kind = models.CharField(max_length=16, choices=JiraMetadataItemKind.choices)
    jira_id = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["metadata", "kind", "jira_id"],
                name="unique_jira_metadata_item_per_kind",
            ),
        ]
        indexes = [
            models.Index(fields=["metadata", "kind"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.name}"
