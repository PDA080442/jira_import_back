"""URL routes for Jira connection API nested under workspaces."""
from django.urls import path

from jira.views import (
    JiraConnectionDeactivateView,
    JiraConnectionDetailView,
    JiraConnectionListCreateView,
    JiraConnectionTestView,
    JiraGuideDetailView,
    JiraGuideListView,
    JiraMetadataSyncView,
    JiraMetadataView,
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
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/<uuid:pk>/metadata/",
        JiraMetadataView.as_view(),
        name="jira-connection-metadata",
    ),
    path(
        "workspaces/<uuid:workspace_id>/jira-connections/<uuid:pk>/sync-metadata/",
        JiraMetadataSyncView.as_view(),
        name="jira-connection-sync-metadata",
    ),
    path(
        "jira/guides/",
        JiraGuideListView.as_view(),
        name="jira-guide-list",
    ),
    path(
        "jira/guides/<slug:slug>/",
        JiraGuideDetailView.as_view(),
        name="jira-guide-detail",
    ),
]
