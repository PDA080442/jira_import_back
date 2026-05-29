from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        from django.conf import settings

        from core.logging import configure_structlog, get_logger

        configure_structlog(json_logs=getattr(settings, "STRUCTLOG_JSON", True))
        logger = get_logger(__name__)
        logger.info(
            "core_app_ready",
            debug=settings.DEBUG,
            database_engine=settings.DATABASES["default"].get("ENGINE"),
            cache_backend=settings.CACHES["default"]["BACKEND"],
        )
