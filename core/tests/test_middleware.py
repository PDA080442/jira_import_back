import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from core.context import TRACE_ID_HEADER
from core.middleware import TraceIdMiddleware


@pytest.fixture
def rf():
    return RequestFactory()


def _get_response(request):
    return HttpResponse("ok")


def test_trace_id_generated_when_missing(rf):
    middleware = TraceIdMiddleware(_get_response)
    request = rf.get("/health/")
    response = middleware(request)

    assert hasattr(request, "trace_id")
    assert request.trace_id
    assert response[TRACE_ID_HEADER] == request.trace_id


def test_trace_id_preserved_from_header(rf):
    middleware = TraceIdMiddleware(_get_response)
    request = rf.get("/health/", headers={TRACE_ID_HEADER: "client-trace"})
    response = middleware(request)

    assert request.trace_id == "client-trace"
    assert response[TRACE_ID_HEADER] == "client-trace"
