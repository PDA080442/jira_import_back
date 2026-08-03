"""Service-level tests for source presets."""
import pytest

from core.exceptions import ApiError
from sources.models import PresetBindingStatus, PresetSourceType, SourceParseStatus
from sources.services import presets as presets_service
from sources.tests.factories import (
    SourceSheetFactory,
    create_source_file,
    create_source_preset,
)
from tenants.tests.factories import create_workspace_with_owner

pytestmark = pytest.mark.django_db


def test_create_preset_and_bump_version():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    preset = presets_service.create_preset(
        workspace_id=workspace.id,
        user=user,
        name="CSV Default",
        source_type=PresetSourceType.FILE,
        settings={"delimiter": "semicolon"},
    )
    assert preset.version == 1

    updated = presets_service.update_preset(
        preset=preset,
        user=user,
        settings={"delimiter": "comma", "encoding": "utf-8"},
    )
    assert updated.version == 2


def test_binding_is_stale_when_version_differs():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    preset = create_source_preset(workspace=workspace, user=user, version=2)
    binding = presets_service.create_initial_binding(
        preset=preset,
        user=user,
        source_type=PresetSourceType.FILE,
        source_id=create_source_file(workspace=workspace, user=user).id,
        settings=preset.settings,
    )
    binding.applied_version = 1
    binding.save(update_fields=["applied_version"])
    assert presets_service.binding_is_stale(binding) is True


def test_validate_preset_type_mismatch():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    preset = create_source_preset(workspace=workspace, user=user, source_type=PresetSourceType.FILE)
    source = create_source_file(workspace=workspace, user=user, status=SourceParseStatus.READY)

    with pytest.raises(ApiError) as exc:
        presets_service.validate_preset_compatibility(
            preset,
            source_type=PresetSourceType.GOOGLE,
            source=source,
        )
    assert exc.value.status_code == 400
    assert "preset_id" in (exc.value.field_errors or {})


def test_validate_missing_columns_on_ready_source():
    workspace = create_workspace_with_owner()
    user = workspace.owner
    preset = create_source_preset(
        workspace=workspace,
        user=user,
        settings={"selected_columns": ["MissingCol"]},
    )
    source = create_source_file(workspace=workspace, user=user, status=SourceParseStatus.READY)
    SourceSheetFactory(source_file=source)

    with pytest.raises(ApiError) as exc:
        presets_service.validate_preset_compatibility(
            preset,
            source_type=PresetSourceType.FILE,
            source=source,
        )
    assert "settings.selected_columns" in (exc.value.field_errors or {})


def test_apply_preset_updates_overrides(monkeypatch):
    workspace = create_workspace_with_owner()
    user = workspace.owner
    preset = create_source_preset(
        workspace=workspace,
        user=user,
        settings={"delimiter": "semicolon", "encoding": "cp1251"},
    )
    source = create_source_file(workspace=workspace, user=user, status=SourceParseStatus.READY)
    SourceSheetFactory(source_file=source)
    monkeypatch.setattr("sources.tasks.parse_source_file.delay", lambda *_a, **_k: None)

    binding = presets_service.apply_preset_to_source(
        preset=preset,
        user=user,
        source_type=PresetSourceType.FILE,
        source=source,
    )
    source.refresh_from_db()
    assert source.delimiter_override == ";"
    assert source.encoding_override == "cp1251"
    assert binding.status == PresetBindingStatus.APPLIED
    assert binding.applied_version == preset.version
