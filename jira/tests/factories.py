"""Test factories for Jira connections."""
import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import ActiveUserFactory
from jira.models import JiraConnection, JiraTestStatus
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
