"""Service tests for source snapshots."""
import pytest
from django.test import override_settings

from core.exceptions import ApiError
from sources.models import PresetSourceType, SourceRefreshRun, SourceSnapshot
from sources.services.parsing import run_parse
from sources.services import snapshots as snapshots_service
from sources.tests.factories import make_uploaded_csv
from sources.services import files as files_service
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner_workspace(monkeypatch):
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *a, **k: None)
    workspace = create_workspace_with_owner()
    return workspace, workspace.owner


def test_run_parse_creates_snapshot_and_refresh_run(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(content="A,B\n1,2\n3,4\n"),
    )
    run_parse(str(source.id))
    source.refresh_from_db()

    assert source.active_snapshot_id is not None
    snapshot = source.active_snapshot
    assert snapshot.is_active is True
    assert snapshot.row_count == 2
    assert len(snapshot.data["sheets"][0]["rows"]) == 2
    assert SourceRefreshRun.objects.filter(source_id=source.id).count() == 1


def test_second_parse_switches_active_snapshot(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(content="A,B\n1,2\n"),
    )
    run_parse(str(source.id), trigger="parse", from_where="upload")
    source.refresh_from_db()
    first_id = source.active_snapshot_id

    run_parse(str(source.id), trigger="reparse", from_where="reparse")
    source.refresh_from_db()
    assert source.active_snapshot_id != first_id
    assert SourceSnapshot.objects.filter(source_id=source.id, is_active=True).count() == 1
    assert SourceSnapshot.objects.filter(pk=first_id, is_active=False).exists()


def test_resolve_snapshot_for_job(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(),
    )
    run_parse(str(source.id))
    source.refresh_from_db()

    resolved = snapshots_service.resolve_snapshot_for_job(
        source_type=PresetSourceType.FILE,
        source_id=source.id,
    )
    assert resolved.id == source.active_snapshot_id

    with pytest.raises(ApiError):
        snapshots_service.resolve_snapshot_for_job(
            source_type=PresetSourceType.FILE,
            source_id=source.id,
            snapshot_id="00000000-0000-0000-0000-000000000099",
        )


@override_settings(SOURCE_SNAPSHOT_MAX_ROWS=1)
def test_truncate_snapshot(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(content="A,B\n1,2\n3,4\n5,6\n"),
    )
    run_parse(str(source.id))
    source.refresh_from_db()
    assert source.active_snapshot.is_truncated is True
    assert source.active_snapshot.row_count == 1


def test_compare_snapshots(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(content="A,B\n1,2\n"),
    )
    run_parse(str(source.id))
    run_parse(str(source.id), trigger="reparse", from_where="reparse")
    result = snapshots_service.compare_for_source(
        workspace_id=workspace.id,
        user=user,
        source_type=PresetSourceType.FILE,
        source_id=source.id,
    )
    assert "summary" in result
    assert result["current_id"]
    assert result["previous_id"]


@override_settings(SOURCE_SNAPSHOT_RETENTION_COUNT=1, SOURCE_SNAPSHOT_RETENTION_DAYS=30)
def test_cleanup_keeps_active(owner_workspace):
    workspace, user = owner_workspace
    source = files_service.create_source_file(
        workspace_id=workspace.id,
        user=user,
        upload=make_uploaded_csv(content="A,B\n1,2\n"),
    )
    run_parse(str(source.id))
    run_parse(str(source.id), trigger="reparse", from_where="reparse")
    run_parse(str(source.id), trigger="reparse", from_where="reparse")
    source.refresh_from_db()
    active_id = source.active_snapshot_id
    assert SourceSnapshot.objects.filter(source_id=source.id).count() == 3

    snapshots_service.cleanup_old_snapshots()
    assert SourceSnapshot.objects.filter(pk=active_id, is_active=True).exists()
    # active + up to 1 inactive kept
    assert SourceSnapshot.objects.filter(source_id=source.id).count() <= 2
