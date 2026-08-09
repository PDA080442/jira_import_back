from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DB_CONN_MAX_AGE=(int, 0),
    DB_CONNECT_TIMEOUT=(int, 10),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_celery_beat",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "tenants.apps.TenantsConfig",
    "jira.apps.JiraConfig",
    "sources.apps.SourcesConfig",
    "templates.apps.TemplatesConfig",
    "imports.apps.ImportsConfig",
    "publishing.apps.PublishingConfig",
    "audit.apps.AuditConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.TraceIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "project_templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


def configure_database(url: str) -> dict:
    db_settings = env.db_url_config(url)
    db_settings["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE")
    db_settings.setdefault("OPTIONS", {})
    db_settings["OPTIONS"]["connect_timeout"] = env.int("DB_CONNECT_TIMEOUT")
    return db_settings


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

SOURCE_FILE_MAX_SIZE_BYTES = env.int("SOURCE_FILE_MAX_SIZE_BYTES", default=10 * 1024 * 1024)
SOURCE_FILE_PREVIEW_ROWS = env.int("SOURCE_FILE_PREVIEW_ROWS", default=20)
SOURCE_SNAPSHOT_MAX_ROWS = env.int("SOURCE_SNAPSHOT_MAX_ROWS", default=50_000)
SOURCE_SNAPSHOT_RETENTION_COUNT = env.int("SOURCE_SNAPSHOT_RETENTION_COUNT", default=10)
SOURCE_SNAPSHOT_RETENTION_DAYS = env.int("SOURCE_SNAPSHOT_RETENTION_DAYS", default=30)
FILE_UPLOAD_MAX_MEMORY_SIZE = max(SOURCE_FILE_MAX_SIZE_BYTES, 2621440)
DATA_UPLOAD_MAX_MEMORY_SIZE = max(SOURCE_FILE_MAX_SIZE_BYTES, 2621440)

GOOGLE_SERVICE_ACCOUNT_FILE = env("GOOGLE_SERVICE_ACCOUNT_FILE", default="")
GOOGLE_SERVICE_ACCOUNT_JSON = env("GOOGLE_SERVICE_ACCOUNT_JSON", default="")
GOOGLE_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Jira Backlog Import API",
    "DESCRIPTION": (
        "REST API for Jira Backlog Import Service (EP1–EP3). "
        "Unified errors: `{ traceId, code, message, fieldErrors }`. "
        "Authenticated endpoints require `Authorization: Bearer <access>` JWT. "
        "Optional header `X-Trace-Id` for correlation."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "TAGS": [
        {"name": "Health", "description": "Liveness and readiness probes (no auth)."},
        {"name": "Auth", "description": "Registration, login, JWT refresh, password reset."},
        {"name": "Profile", "description": "Authenticated user profile (`/api/me/`)."},
        {
            "name": "Workspaces",
            "description": (
                "Workspace CRUD, members, and email invites. "
                "Access checks in services: non-members get 404 NOT_FOUND."
            ),
        },
        {
            "name": "Jira Connections",
            "description": (
                "Jira Cloud connections per workspace. "
                "API tokens encrypted at rest; never returned in API responses."
            ),
        },
        {
            "name": "Jira Metadata",
            "description": (
                "Cached Jira project metadata per connection: issue types, fields, "
                "priorities, statuses, components, labels, boards, sprints. "
                "Sync runs in background via Celery."
            ),
        },
        {
            "name": "Jira Guides",
            "description": (
                "Editable onboarding/help content stored in DB and fetched by the "
                "frontend (e.g. Jira connection setup instructions)."
            ),
        },
        {
            "name": "Source Files",
            "description": (
                "Excel/CSV file uploads per workspace. Upload returns immediately; "
                "parsing runs in Celery and exposes sheets, columns, and preview rows."
            ),
        },
        {
            "name": "Google Sheet Sources",
            "description": (
                "Google Sheets connected by URL or spreadsheet ID. Snapshot refresh runs "
                "in Celery via global service account; exposes tabs, columns, preview rows."
            ),
        },
    ],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT access token from POST /api/auth/login/",
            },
        },
    },
    "SECURITY": [{"BearerAuth": []}],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
    },
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-trace-id",
    "x-workspace-id",
]

STRUCTLOG_JSON = env.bool("STRUCTLOG_JSON", default=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    },
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

HEALTHCHECK_CELERY_TIMEOUT = env.float("HEALTHCHECK_CELERY_TIMEOUT", default=1.0)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days=env.int("ACCESS_TOKEN_LIFETIME_DAYS", default=7)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("REFRESH_TOKEN_LIFETIME_DAYS", default=30)),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

EMAIL_VERIFICATION_TTL_HOURS = env.int("EMAIL_VERIFICATION_TTL_HOURS", default=24)
PASSWORD_RESET_TTL_HOURS = env.int("PASSWORD_RESET_TTL_HOURS", default=24)
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@jira-import.local")
WORKSPACE_INVITE_TTL_HOURS = env.int("WORKSPACE_INVITE_TTL_HOURS", default=168)

# Fernet key for encrypting Jira API tokens at rest (generate: Fernet.generate_key())
FIELD_ENCRYPTION_KEY = env(
    "FIELD_ENCRYPTION_KEY",
    default="Jx7ifvzS8Bq5tUkIooy9UMO3MjmcQ123w7LIXMCk_hs=",
)
