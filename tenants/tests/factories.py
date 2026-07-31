import factory
from factory.django import DjangoModelFactory

from accounts.tests.factories import ActiveUserFactory
from tenants.models import Workspace, WorkspaceMembership, WorkspaceRole
from tenants.services.workspace import create_workspace


class WorkspaceFactory(DjangoModelFactory):
    class Meta:
        model = Workspace

    name = factory.Sequence(lambda n: f"Workspace {n}")
    slug = factory.Sequence(lambda n: f"workspace-{n}")
    owner = factory.SubFactory(ActiveUserFactory)


class WorkspaceMembershipFactory(DjangoModelFactory):
    class Meta:
        model = WorkspaceMembership

    workspace = factory.SubFactory(WorkspaceFactory)
    user = factory.SubFactory(ActiveUserFactory)
    role = WorkspaceRole.VIEWER


def create_workspace_with_owner(*, user=None, name="Test Workspace"):
    user = user or ActiveUserFactory()
    return create_workspace(user=user, name=name)
