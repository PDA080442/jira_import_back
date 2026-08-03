"""URL routes for source file API nested under workspaces."""
from django.urls import path

from sources.views import (
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
]
