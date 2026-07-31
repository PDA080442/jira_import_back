from drf_spectacular.utils import extend_schema_view
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.logging import get_logger
from core.openapi_health import health_live_schema, health_ready_schema
from core.serializers.health import HealthLiveSerializer, HealthReadySerializer
from core.services.health import is_ready, run_readiness_checks

logger = get_logger(__name__)


@extend_schema_view(get=health_live_schema)
class HealthLiveView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get"]

    def get(self, request):
        payload = {"status": "ok"}
        serializer = HealthLiveSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


@extend_schema_view(get=health_ready_schema)
class HealthReadyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get"]

    def get(self, request):
        checks = run_readiness_checks()
        ready = is_ready(checks)
        payload = {
            "status": "ok" if ready else "error",
            "checks": checks,
        }
        serializer = HealthReadySerializer(data=payload)
        serializer.is_valid(raise_exception=True)

        if not ready:
            from audit.services.log_action import log_action

            log_action(
                action="readiness.check.failed",
                entity_type="system",
                entity_id="ready",
                trace_id=getattr(request, "trace_id", None),
                payload={"checks": checks},
            )
            logger.warning("readiness_check_failed", checks=checks)

        status_code = 200 if ready else 503
        return Response(serializer.data, status=status_code)
