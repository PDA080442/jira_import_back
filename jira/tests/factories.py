"""Test factories for Jira connections and metadata."""
import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from accounts.tests.factories import ActiveUserFactory
from jira.models import (
    JiraBoard,
    JiraConnection,
    JiraField,
    JiraIssueType,
    JiraMetadataItem,
    JiraMetadataItemKind,
    JiraProjectMetadata,
    JiraSprint,
    JiraSyncStatus,
    JiraTestStatus,
)
from jira.services.crypto import encrypt_secret
from tenants.tests.factories import create_workspace_with_owner


class JiraConnectionFactory(DjangoModelFactory):
    class Meta:
        model = JiraConnection

    workspace = factory.SubFactory("tenants.tests.factories.WorkspaceFactory")
    name = factory.Sequence(lambda n: f"Jira Connection {n}")
    base_url = "https://example.atlassian.net"
    email = factory.LazyAttribute(lambda o: o.workspace.owner.email)
    api_token_encrypted = factory.LazyFunction(lambda: encrypt_secret("test-api-token"))
    project_key = "PROJ"
    board_id = ""
    extra = factory.LazyFunction(dict)
    is_active = True
    last_test_status = JiraTestStatus.UNKNOWN
    created_by = factory.LazyAttribute(lambda o: o.workspace.owner)


class JiraProjectMetadataFactory(DjangoModelFactory):
    class Meta:
        model = JiraProjectMetadata

    connection = factory.SubFactory(JiraConnectionFactory)
    project_id = "10001"
    project_name = "Demo Project"
    project_key = "PROJ"
    status = JiraSyncStatus.FRESH
    fetched_at = factory.LazyFunction(timezone.now)
    ttl_seconds = 3600


def create_jira_connection(*, workspace=None, user=None, **kwargs):
    user = user or ActiveUserFactory()
    workspace = workspace or create_workspace_with_owner(user=user)
    defaults = {
        "workspace": workspace,
        "created_by": user,
        "api_token_encrypted": encrypt_secret(kwargs.pop("api_token", "test-api-token")),
    }
    defaults.update(kwargs)
    return JiraConnection.objects.create(**defaults)


def create_jira_metadata(*, connection=None, **kwargs):
    connection = connection or create_jira_connection()
    defaults = {
        "connection": connection,
        "project_key": connection.project_key,
    }
    defaults.update(kwargs)
    return JiraProjectMetadata.objects.create(**defaults)


def populate_sample_metadata(metadata: JiraProjectMetadata) -> None:
    JiraIssueType.objects.create(
        metadata=metadata,
        jira_id="10001",
        name="Story",
        hierarchy_level=0,
        is_subtask=False,
    )
    JiraField.objects.create(
        metadata=metadata,
        jira_id="summary",
        key="summary",
        name="Summary",
        is_custom=False,
        schema_type="string",
        is_required=True,
        template_field_type="text",
    )
    JiraMetadataItem.objects.create(
        metadata=metadata,
        kind=JiraMetadataItemKind.PRIORITY,
        jira_id="1",
        name="High",
    )
    board = JiraBoard.objects.create(
        metadata=metadata,
        jira_board_id="42",
        name="Scrum board",
        board_type="scrum",
    )
    JiraSprint.objects.create(
        board=board,
        jira_sprint_id="101",
        name="Sprint 1",
        state="active",
    )

