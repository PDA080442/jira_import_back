from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from core.services.health import is_ready, run_readiness_checks


@csrf_exempt
@require_GET
def health_live(request):
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_GET
def health_ready(request):
    checks = run_readiness_checks()
    ready = is_ready(checks)
    payload = {
        "status": "ok" if ready else "error",
        "checks": checks,
    }
    return JsonResponse(payload, status=200 if ready else 503)
