"""OpenAPI schema helpers for health endpoints."""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from core.openapi import TRACE_ID_HEADER
from core.serializers.health import HealthLiveSerializer, HealthReadySerializer

HEALTH_TAG = "Health"

health_live_schema = extend_schema(
    tags=[HEALTH_TAG],
    operation_id="health_live",
    summary="Liveness probe",
    description="Returns 200 if the process is running. No dependency checks.",
    auth=[],
    parameters=[TRACE_ID_HEADER],
    responses={
        200: OpenApiResponse(
            response=HealthLiveSerializer,
            description="Process is alive.",
            examples=[OpenApiExample(name="OK", value={"status": "ok"}, response_only=True)],
        ),
    },
)

health_ready_schema = extend_schema(
    tags=[HEALTH_TAG],
    operation_id="health_ready",
    summary="Readiness probe",
    description=(
        "Checks database, Redis, and Celery broker connectivity. "
        "Returns **503** when any check fails."
    ),
    auth=[],
    parameters=[TRACE_ID_HEADER],
    responses={
        200: OpenApiResponse(
            response=HealthReadySerializer,
            description="All dependencies healthy.",
        ),
        503: OpenApiResponse(
            response=HealthReadySerializer,
            description="One or more dependency checks failed.",
        ),
    },
)
