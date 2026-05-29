import pytest
from rest_framework.test import APIClient

from core.context import TRACE_ID_HEADER


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def trace_id():
    return "test-trace-id-123"


@pytest.fixture
def api_client_with_trace(api_client, trace_id):
    api_client.defaults[TRACE_ID_HEADER] = trace_id
    return api_client
