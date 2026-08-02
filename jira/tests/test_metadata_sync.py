import pytest

from jira.models import (
    JiraField,
    JiraIssueType,
    JiraMetadataItem,
    JiraMetadataItemKind,
    JiraProjectMetadata,
    JiraSprint,
    JiraSyncStatus,
)
from jira.services.jira_client import (
    JiraBoardResult,
    JiraMetadataFetchResult,
    JiraProjectResult,
    JiraSprintResult,
)
from jira.services.metadata import normalize_field_type, run_metadata_sync
from jira.tests.factories import create_jira_connection


def _sample_fetch_result():
    return JiraMetadataFetchResult(
        project=JiraProjectResult(
            project_id="10001",
            project_key="PROJ",
            project_name="Demo Project",
            issue_types=[],
        ),
        issue_types=[
            {
                "id": "10001",
                "name": "Story",
                "subtask": False,
                "hierarchyLevel": 0,
                "description": "User story",
                "iconUrl": "https://example.atlassian.net/icon.png",
            },
        ],
        fields=[
            {
                "id": "customfield_10001",
                "key": "customfield_10001",
                "name": "Story Points",
                "custom": True,
                "schema": {
                    "type": "number",
                    "custom": "com.atlassian.jira.plugin.system.customfieldtypes:float",
                },
            },
            {
                "id": "summary",
                "key": "summary",
                "name": "Summary",
                "custom": False,
                "schema": {"type": "string"},
            },
        ],
        required_field_keys={"summary"},
        priorities=[{"id": "1", "name": "High", "iconUrl": ""}],
        statuses=[{"id": "3", "name": "In Progress", "statusCategory": {"name": "In Progress"}}],
        components=[{"id": "10000", "name": "Backend", "description": ""}],
        labels=["bug", "feature"],
        boards=[JiraBoardResult(board_id="42", name="Scrum board", board_type="scrum")],
        sprints_by_board={
            "42": [
                JiraSprintResult(
                    sprint_id="101",
                    name="Sprint 1",
                    state="active",
                    start_date=None,
                    end_date=None,
                    goal="MVP",
                ),
            ],
        },
    )


def test_normalize_field_type_maps_custom_float_to_number():
    field_data = {
        "custom": True,
        "schema": {
            "type": "number",
            "custom": "com.atlassian.jira.plugin.system.customfieldtypes:float",
        },
    }
    assert normalize_field_type(field_data) == "number"


def test_normalize_field_type_maps_system_string_to_text():
    field_data = {"custom": False, "schema": {"type": "string"}}
    assert normalize_field_type(field_data) == "text"


@pytest.mark.django_db
def test_run_metadata_sync_persists_entities(monkeypatch):
    connection = create_jira_connection()
    monkeypatch.setattr(
        "jira.services.metadata.fetch_project_metadata",
        lambda **kwargs: _sample_fetch_result(),
    )

    run_metadata_sync(str(connection.id))

    metadata = JiraProjectMetadata.objects.get(connection=connection)
    assert metadata.status == JiraSyncStatus.FRESH
    assert metadata.project_name == "Demo Project"
    assert JiraIssueType.objects.filter(metadata=metadata).count() == 1
    assert JiraField.objects.filter(metadata=metadata).count() == 2
    assert JiraField.objects.get(key="summary").is_required is True
    assert JiraField.objects.get(key="customfield_10001").template_field_type == "number"
    assert JiraMetadataItem.objects.filter(metadata=metadata, kind=JiraMetadataItemKind.PRIORITY).count() == 1
    assert JiraMetadataItem.objects.filter(metadata=metadata, kind=JiraMetadataItemKind.LABEL).count() == 2
    assert JiraSprint.objects.filter(board__metadata=metadata).count() == 1


@pytest.mark.django_db
def test_run_metadata_sync_marks_failed_on_client_error(monkeypatch):
    from jira.services.jira_client import JiraClientError

    connection = create_jira_connection()

    def _raise(**kwargs):
        raise JiraClientError("Jira server error.", 500)

    monkeypatch.setattr("jira.services.metadata.fetch_project_metadata", _raise)

    with pytest.raises(JiraClientError):
        run_metadata_sync(str(connection.id))

    metadata = JiraProjectMetadata.objects.get(connection=connection)
    assert metadata.status == JiraSyncStatus.FAILED
    assert metadata.last_error
