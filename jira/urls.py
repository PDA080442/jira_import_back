"""URL routes for Jira connection API nested under workspaces."""
from django.urls import path

from jira.views import (
    JiraConnectionDeactivateView,
    JiraConnectionDetailView,
    JiraConnectionListCreateView,
    JiraConnectionTestView,
)

urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/",
        JiraConnectionListCreateView.as_view(),
        name="jira-connection-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/<uuid:pk>/",
        JiraConnectionDetailView.as_view(),
        name="jira-connection-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/<uuid:pk>/deactivate/",
        JiraConnectionDeactivateView.as_view(),
        name="jira-connection-deactivate",
    ),
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/<uuid:pk>/test/",
        JiraConnectionTestView.as_view(),
        name="jira-connection-test",
    ),
]
