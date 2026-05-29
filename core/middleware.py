from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from core.context import TRACE_ID_HEADER, resolve_trace_id, set_trace_id


class TraceIdMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        trace_id = resolve_trace_id(request.headers.get(TRACE_ID_HEADER))
        set_trace_id(trace_id)
        request.trace_id = trace_id

        response = self.get_response(request)
        response[TRACE_ID_HEADER] = trace_id
        return response
