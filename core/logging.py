import logging
import re
from typing import Any

import structlog

from core.context import get_trace_id

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "api_token",
        "authorization",
        "secret",
        "secret_key",
        "api_key",
    }
)

REDACTED = "***REDACTED***"
DATABASE_URL_PATTERN = re.compile(r"(postgres(?:ql)?://[^:]+:)([^@]+)(@)")


def redact_value(key: str, value: Any) -> Any:
    key_lower = key.lower()
    if key_lower in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, str):
        if "://" in value and "@" in value:
            return DATABASE_URL_PATTERN.sub(r"\1" + REDACTED + r"\3", value)
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_mapping(item) if isinstance(item, dict) else item for item in value]
    return value


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    return {key: redact_value(key, value) for key, value in data.items()}


def add_trace_id(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    trace_id = get_trace_id()
    if trace_id:
        event_dict["traceId"] = trace_id
    return event_dict


def configure_structlog(*, json_logs: bool = True) -> None:
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_trace_id,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
