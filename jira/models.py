"""ORM models for Jira Cloud connections."""
import uuid

from django.conf import settings
from django.db import models


class JiraTestStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    SUCCESS = "success", "Success"
    FAILED = "failed", "Failed"


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
