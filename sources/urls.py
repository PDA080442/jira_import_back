"""URL routes for source file API nested under workspaces."""
from django.urls import path

from sources.views import (
    GoogleSheetSourceDeactivateView,
    GoogleSheetSourceDetailView,
    GoogleSheetSourceListCreateView,
    GoogleSheetSourceRefreshView,
    SourceFileDeactivateView,
    SourceFileDetailView,
    SourceFileListCreateView,
    SourceFileReparseView,
)

urlpatterns = [
    path(
        "workspaces/<uuid:workspace_id>/source-files/",
        SourceFileListCreateView.as_view(),
        name="source-file-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/source-files/<uuid:pk>/",
        SourceFileDetailView.as_view(),
        name="source-file-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/source-files/<uuid:pk>/deactivate/",
        SourceFileDeactivateView.as_view(),
        name="source-file-deactivate",
    ),
    path(
        "workspaces/<uuid:workspace_id>/source-files/<uuid:pk>/reparse/",
        SourceFileReparseView.as_view(),
        name="source-file-reparse",
    ),
    path(
        "workspaces/<uuid:workspace_id>/google-sheet-sources/",
        GoogleSheetSourceListCreateView.as_view(),
        name="google-sheet-source-list-create",
    ),
    path(
        "workspaces/<uuid:workspace_id>/google-sheet-sources/<uuid:pk>/",
        GoogleSheetSourceDetailView.as_view(),
        name="google-sheet-source-detail",
    ),
    path(
        "workspaces/<uuid:workspace_id>/google-sheet-sources/<uuid:pk>/deactivate/",
        GoogleSheetSourceDeactivateView.as_view(),
        name="google-sheet-source-deactivate",
    ),
    path(
        "workspaces/<uuid:workspace_id>/google-sheet-sources/<uuid:pk>/refresh/",
        GoogleSheetSourceRefreshView.as_view(),
        name="google-sheet-source-refresh",
    ),
]
