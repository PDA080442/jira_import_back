"""Synchronous Jira connection test."""
from django.utils import timezone

from accounts.models import User
from audit.services.log_action import log_action
from core.logging import get_logger
from jira.models import JiraConnection, JiraTestStatus
from jira.services.connection import _require_admin
from jira.services.crypto import decrypt_secret
from jira.services.jira_client import JiraAuthError, JiraClientError, verify_credentials

logger = get_logger("jira.test")


def run_connection_test(*, connection: JiraConnection, user: User) -> dict:
    _require_admin(user=user, workspace=connection.workspace, action="test")

    tested_at = timezone.now()
    try:
        api_token = decrypt_secret(connection.api_token_encrypted)
        myself = verify_credentials(
            base_url=connection.base_url,
            email=connection.email,
            api_token=api_token,
        )
        connection.last_test_at = tested_at
        connection.last_test_status = JiraTestStatus.SUCCESS
        connection.last_test_error = ""
        connection.save(update_fields=["last_test_at", "last_test_status", "last_test_error", "updated_at"])

        result = {
            "status": JiraTestStatus.SUCCESS,
            "tested_at": tested_at,
            "detail": "Connection successful.",
            "account": {
                "account_id": myself.account_id,
                "display_name": myself.display_name,
                "email_address": myself.email_address,
            },
        }
        log_action(
            action="jira_connection.test.success",
            entity_type="jira_connection",
            entity_id=str(connection.id),
            actor=user,
            payload={"connection_id": str(connection.id), "status": "success"},
        )
        logger.info("jira_connection_test_success", connection_id=str(connection.id))
        return result

    except JiraAuthError as exc:
        error_message = str(exc)
        connection.last_test_at = tested_at
        connection.last_test_status = JiraTestStatus.FAILED
        connection.last_test_error = error_message[:512]
        connection.save(update_fields=["last_test_at", "last_test_status", "last_test_error", "updated_at"])

        log_action(
            action="jira_connection.test.failed",
            entity_type="jira_connection",
            entity_id=str(connection.id),
            actor=user,
            payload={
                "connection_id": str(connection.id),
                "status": "failed",
                "http_status": exc.status_code,
            },
        )
        logger.warning(
            "jira_connection_test_failed",
            connection_id=str(connection.id),
            reason="auth",
            http_status=exc.status_code,
        )
        return {
            "status": JiraTestStatus.FAILED,
            "tested_at": tested_at,
            "detail": error_message,
            "account": None,
        }

    except (JiraClientError, Exception) as exc:
        error_message = str(exc) if str(exc) else "Connection test failed."
        connection.last_test_at = tested_at
        connection.last_test_status = JiraTestStatus.FAILED
        connection.last_test_error = error_message[:512]
        connection.save(update_fields=["last_test_at", "last_test_status", "last_test_error", "updated_at"])

        http_status = getattr(exc, "status_code", None)
        log_action(
            action="jira_connection.test.failed",
            entity_type="jira_connection",
            entity_id=str(connection.id),
            actor=user,
            payload={
                "connection_id": str(connection.id),
                "status": "failed",
                "http_status": http_status,
            },
        )
        logger.warning(
            "jira_connection_test_failed",
            connection_id=str(connection.id),
            reason="client",
            http_status=http_status,
        )
        return {
            "status": JiraTestStatus.FAILED,
            "tested_at": tested_at,
            "detail": error_message,
            "account": None,
        }
