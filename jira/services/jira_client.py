"""HTTP client for Jira Cloud REST API."""
from dataclasses import dataclass

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from jira.constants import JIRA_MYSELF_PATH, JIRA_REQUEST_TIMEOUT_SECONDS, JIRA_TEST_MAX_RETRIES


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


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, JiraClientError):
        return exc.status_code >= 500 or exc.status_code == 429
    return False


@retry(
    retry=retry_if_exception(_should_retry),
    stop=stop_after_attempt(JIRA_TEST_MAX_RETRIES),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def _request_myself(*, base_url: str, email: str, api_token: str) -> httpx.Response:
    url = f"{_normalize_base_url(base_url)}{JIRA_MYSELF_PATH}"
    with httpx.Client(timeout=JIRA_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(url, auth=(email, api_token))
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


def verify_credentials(*, base_url: str, email: str, api_token: str) -> JiraMyselfResult:
    """Call GET /rest/api/3/myself; retries on network/5xx/429 only."""
    response = _request_myself(base_url=base_url, email=email, api_token=api_token)
    data = response.json()
    return JiraMyselfResult(
        account_id=data.get("accountId", ""),
        display_name=data.get("displayName", ""),
        email_address=data.get("emailAddress", ""),
    )
