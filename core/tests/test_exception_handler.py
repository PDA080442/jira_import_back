from rest_framework.exceptions import NotFound, ValidationError

from core.context import set_trace_id
from core.exceptions import ApiError, custom_exception_handler


def test_validation_error_returns_field_errors():
    set_trace_id("trace-validation")
    exc = ValidationError({"name": ["This field is required."]})
    response = custom_exception_handler(exc, context={})

    assert response.status_code == 400
    assert response.data["traceId"] == "trace-validation"
    assert response.data["code"] == "VALIDATION_ERROR"
    assert response.data["fieldErrors"]["name"] == ["This field is required."]


def test_api_error_custom_payload():
    set_trace_id("trace-api")
    exc = ApiError(
        detail="Forbidden action.",
        code="FORBIDDEN",
        field_errors={"workspace": ["Not allowed."]},
        status_code=403,
    )
    response = custom_exception_handler(exc, context={})

    assert response.status_code == 403
    assert response.data["code"] == "FORBIDDEN"
    assert response.data["fieldErrors"]["workspace"] == ["Not allowed."]


def test_not_found_mapped_to_unified_format():
    set_trace_id("trace-404")
    response = custom_exception_handler(NotFound("Missing."), context={})

    assert response.status_code == 404
    assert response.data["code"] == "NOT_FOUND"
    assert response.data["traceId"] == "trace-404"


def test_unknown_exception_returns_internal_error():
    set_trace_id("trace-500")
    response = custom_exception_handler(Exception("boom"), context={})

    assert response.status_code == 500
    assert response.data["code"] == "INTERNAL_ERROR"
