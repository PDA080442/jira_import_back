from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

from core.context import get_trace_id


class ApiError(APIException):
    default_code = "API_ERROR"
    default_detail = "Request failed."

    def __init__(
        self,
        detail=None,
        code=None,
        field_errors=None,
        status_code=None,
    ):
        if code is not None:
            self.default_code = code
        super().__init__(detail, code)
        self.field_errors = field_errors or {}
        if status_code is not None:
            self.status_code = status_code


def build_error_payload(code: str, message: str, field_errors=None) -> dict:
    return {
        "traceId": get_trace_id() or "",
        "code": code,
        "message": message,
        "fieldErrors": field_errors or {},
    }


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if isinstance(exc, ApiError):
        return _json_response(
            exc.status_code,
            build_error_payload(
                code=exc.default_code,
                message=str(exc.detail),
                field_errors=exc.field_errors,
            ),
        )

    if isinstance(exc, ValidationError):
        field_errors = _normalize_field_errors(exc.detail)
        return _json_response(
            status.HTTP_400_BAD_REQUEST,
            build_error_payload(
                code="VALIDATION_ERROR",
                message="Invalid input.",
                field_errors=field_errors,
            ),
        )

    if response is not None:
        code = _status_to_code(response.status_code)
        message = _extract_message(response.data)
        field_errors = {}
        if response.status_code == status.HTTP_400_BAD_REQUEST and isinstance(response.data, dict):
            field_errors = _normalize_field_errors(response.data)
            message = "Invalid input."
        return _json_response(
            response.status_code,
            build_error_payload(code=code, message=message, field_errors=field_errors),
        )

    return _json_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        build_error_payload(
            code="INTERNAL_ERROR",
            message="Internal server error.",
        ),
    )


def _json_response(status_code, payload):
    from rest_framework.response import Response

    return Response(payload, status=status_code)


def _normalize_field_errors(detail) -> dict:
    if isinstance(detail, dict):
        normalized = {}
        for key, value in detail.items():
            if isinstance(value, list):
                normalized[key] = [str(item) for item in value]
            else:
                normalized[key] = [str(value)]
        return normalized
    if isinstance(detail, list):
        return {"non_field_errors": [str(item) for item in detail]}
    return {"non_field_errors": [str(detail)]}


def _extract_message(data) -> str:
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        return "Request failed."
    if isinstance(data, list):
        return str(data[0]) if data else "Request failed."
    return str(data)


def _status_to_code(status_code: int) -> str:
    mapping = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    }
    return mapping.get(status_code, "API_ERROR")
