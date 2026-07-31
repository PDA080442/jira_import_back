"""URL routes for workspace tenant API."""
from django.urls import path

from tenants.views import (
    WorkspaceDetailView,
    WorkspaceInviteAcceptView,
    WorkspaceInviteCreateView,
    WorkspaceListCreateView,
    WorkspaceMemberListView,
)

urlpatterns = [
    path("workspaces/", WorkspaceListCreateView.as_view(), name="workspace-list-create"),
    path("workspaces/invites/accept/", WorkspaceInviteAcceptView.as_view(), name="workspace-invite-accept"),
    path("workspaces/<uuid:pk>/", WorkspaceDetailView.as_view(), name="workspace-detail"),
    path("workspaces/<uuid:pk>/members/", WorkspaceMemberListView.as_view(), name="workspace-members"),
    path("workspaces/<uuid:pk>/invites/", WorkspaceInviteCreateView.as_view(), name="workspace-invite-create"),
]
