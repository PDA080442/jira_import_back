import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)

TRACE_ID_HEADER = "X-Trace-Id"


def get_trace_id() -> str | None:
    return trace_id_var.get()


def set_trace_id(trace_id: str | None) -> None:
    trace_id_var.set(trace_id)


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def resolve_trace_id(incoming: str | None) -> str:
    if incoming and incoming.strip():
        return incoming.strip()
    return generate_trace_id()
