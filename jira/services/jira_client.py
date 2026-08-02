"""HTTP client for Jira Cloud REST API."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from jira.constants import (
    JIRA_AGILE_BOARD_SPRINTS_PATH,
    JIRA_AGILE_BOARDS_PATH,
    JIRA_CREATE_META_PATH,
    JIRA_FIELDS_PATH,
    JIRA_ISSUE_TYPES_PATH,
    JIRA_LABELS_PAGE_SIZE,
    JIRA_LABELS_PATH,
    JIRA_METADATA_MAX_RETRIES,
    JIRA_MYSELF_PATH,
    JIRA_PRIORITIES_PATH,
    JIRA_PROJECT_COMPONENTS_PATH,
    JIRA_PROJECT_PATH,
    JIRA_PROJECT_STATUSES_PATH,
    JIRA_REQUEST_TIMEOUT_SECONDS,
    JIRA_TEST_MAX_RETRIES,
)


class JiraAuthError(Exception):
    """401/403 from Jira — do not retry."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class JiraClientError(Exception):
    """Other Jira HTTP errors."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class JiraMyselfResult:
    account_id: str
    display_name: str
    email_address: str


@dataclass(frozen=True)
class JiraProjectResult:
    project_id: str
    project_key: str
    project_name: str
    issue_types: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class JiraBoardResult:
    board_id: str
    name: str
    board_type: str


@dataclass(frozen=True)
class JiraSprintResult:
    sprint_id: str
    name: str
    state: str
    start_date: datetime | None
    end_date: datetime | None
    goal: str


@dataclass(frozen=True)
class JiraMetadataFetchResult:
    project: JiraProjectResult
    issue_types: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    required_field_keys: set[str]
    priorities: list[dict[str, Any]]
    statuses: list[dict[str, Any]]
    components: list[dict[str, Any]]
    labels: list[str]
    boards: list[JiraBoardResult]
    sprints_by_board: dict[str, list[JiraSprintResult]]


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, JiraClientError):
        return exc.status_code >= 500 or exc.status_code == 429
    return False


def _parse_jira_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _handle_response(response: httpx.Response) -> httpx.Response:
    if response.status_code in (401, 403):
        raise JiraAuthError(
            "Invalid Jira credentials or insufficient permissions.",
            response.status_code,
        )
    if response.status_code == 429:
        raise JiraClientError("Jira rate limit exceeded.", 429)
    if response.status_code >= 500:
        raise JiraClientError("Jira server error.", response.status_code)
    if response.status_code >= 400:
        raise JiraClientError("Jira request failed.", response.status_code)
    return response


@retry(
    retry=retry_if_exception(_should_retry),
    stop=stop_after_attempt(JIRA_METADATA_MAX_RETRIES),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    reraise=True,
)
def _request(
    *,
    base_url: str,
    email: str,
    api_token: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> httpx.Response:
    url = f"{_normalize_base_url(base_url)}{path}"
    with httpx.Client(timeout=JIRA_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(url, auth=(email, api_token), params=params or {})
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                import time

                time.sleep(float(retry_after))
            except (TypeError, ValueError):
                pass
        raise JiraClientError("Jira rate limit exceeded.", 429)
    return _handle_response(response)


@retry(
    retry=retry_if_exception(_should_retry),
    stop=stop_after_attempt(JIRA_TEST_MAX_RETRIES),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def _request_myself(*, base_url: str, email: str, api_token: str) -> httpx.Response:
    return _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_MYSELF_PATH,
    )


def verify_credentials(*, base_url: str, email: str, api_token: str) -> JiraMyselfResult:
    """Call GET /rest/api/3/myself; retries on network/5xx/429 only."""
    response = _request_myself(base_url=base_url, email=email, api_token=api_token)
    data = response.json()
    return JiraMyselfResult(
        account_id=data.get("accountId", ""),
        display_name=data.get("displayName", ""),
        email_address=data.get("emailAddress", ""),
    )


def fetch_project(*, base_url: str, email: str, api_token: str, project_key: str) -> JiraProjectResult:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_PROJECT_PATH.format(project_key=project_key),
    )
    data = response.json()
    return JiraProjectResult(
        project_id=str(data.get("id", "")),
        project_key=data.get("key", project_key),
        project_name=data.get("name", ""),
        issue_types=data.get("issueTypes") or [],
    )


def fetch_issue_types(*, base_url: str, email: str, api_token: str) -> list[dict[str, Any]]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_ISSUE_TYPES_PATH,
    )
    return response.json()


def fetch_fields(*, base_url: str, email: str, api_token: str) -> list[dict[str, Any]]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_FIELDS_PATH,
    )
    return response.json()


def fetch_required_field_keys(
    *,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
) -> set[str]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_CREATE_META_PATH,
        params={
            "projectKeys": project_key,
            "expand": "projects.issuetypes.fields",
        },
    )
    required_keys: set[str] = set()
    for project in response.json().get("projects") or []:
        for issue_type in project.get("issuetypes") or []:
            for field_key, field_data in (issue_type.get("fields") or {}).items():
                if field_data.get("required"):
                    required_keys.add(field_key)
    return required_keys


def fetch_priorities(*, base_url: str, email: str, api_token: str) -> list[dict[str, Any]]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_PRIORITIES_PATH,
    )
    return response.json()


def fetch_statuses(
    *,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
) -> list[dict[str, Any]]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_PROJECT_STATUSES_PATH.format(project_key=project_key),
    )
    statuses: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in response.json():
        for status in entry.get("statuses") or []:
            status_id = str(status.get("id", ""))
            if status_id and status_id not in seen:
                seen.add(status_id)
                statuses.append(status)
    return statuses


def fetch_components(
    *,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
) -> list[dict[str, Any]]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_PROJECT_COMPONENTS_PATH.format(project_key=project_key),
    )
    return response.json()


def fetch_labels(*, base_url: str, email: str, api_token: str) -> list[str]:
    labels: list[str] = []
    start_at = 0
    while True:
        response = _request(
            base_url=base_url,
            email=email,
            api_token=api_token,
            path=JIRA_LABELS_PATH,
            params={"startAt": start_at, "maxResults": JIRA_LABELS_PAGE_SIZE},
        )
        data = response.json()
        values = data.get("values") or []
        labels.extend(values)
        if data.get("isLast", True) or not values:
            break
        start_at += len(values)
    return labels


def fetch_boards(
    *,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
) -> list[JiraBoardResult]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_AGILE_BOARDS_PATH,
        params={"projectKeyOrId": project_key},
    )
    boards: list[JiraBoardResult] = []
    for item in response.json().get("values") or []:
        board_type = (item.get("type") or "").lower()
        if board_type not in ("scrum", "kanban"):
            continue
        boards.append(
            JiraBoardResult(
                board_id=str(item.get("id", "")),
                name=item.get("name", ""),
                board_type=board_type,
            ),
        )
    return boards


def fetch_sprints(
    *,
    base_url: str,
    email: str,
    api_token: str,
    board_id: str,
) -> list[JiraSprintResult]:
    response = _request(
        base_url=base_url,
        email=email,
        api_token=api_token,
        path=JIRA_AGILE_BOARD_SPRINTS_PATH.format(board_id=board_id),
        params={"state": "active,future"},
    )
    sprints: list[JiraSprintResult] = []
    for item in response.json().get("values") or []:
        sprints.append(
            JiraSprintResult(
                sprint_id=str(item.get("id", "")),
                name=item.get("name", ""),
                state=item.get("state", ""),
                start_date=_parse_jira_datetime(item.get("startDate")),
                end_date=_parse_jira_datetime(item.get("endDate")),
                goal=item.get("goal") or "",
            ),
        )
    return sprints


def fetch_project_metadata(
    *,
    base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    board_id: str = "",
) -> JiraMetadataFetchResult:
    """Fetch all metadata entities for a Jira project."""
    project = fetch_project(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
    )
    issue_types = project.issue_types or fetch_issue_types(
        base_url=base_url,
        email=email,
        api_token=api_token,
    )
    fields = fetch_fields(base_url=base_url, email=email, api_token=api_token)
    required_field_keys = fetch_required_field_keys(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
    )
    priorities = fetch_priorities(base_url=base_url, email=email, api_token=api_token)
    statuses = fetch_statuses(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
    )
    components = fetch_components(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
    )
    labels = fetch_labels(base_url=base_url, email=email, api_token=api_token)
    boards = fetch_boards(
        base_url=base_url,
        email=email,
        api_token=api_token,
        project_key=project_key,
    )

    sprints_by_board: dict[str, list[JiraSprintResult]] = {}
    if board_id:
        sprints_by_board[board_id] = fetch_sprints(
            base_url=base_url,
            email=email,
            api_token=api_token,
            board_id=board_id,
        )
    else:
        for board in boards:
            sprints_by_board[board.board_id] = fetch_sprints(
                base_url=base_url,
                email=email,
                api_token=api_token,
                board_id=board.board_id,
            )

    return JiraMetadataFetchResult(
        project=project,
        issue_types=issue_types,
        fields=fields,
        required_field_keys=required_field_keys,
        priorities=priorities,
        statuses=statuses,
        components=components,
        labels=labels,
        boards=boards,
        sprints_by_board=sprints_by_board,
    )
