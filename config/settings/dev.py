from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

DEFAULT_DATABASE_URL = (
    "postgres://jira_import:jira_import@127.0.0.1:5432/jira_import"
)

DATABASES = {
    "default": configure_database(
        env("DATABASE_URL", default=DEFAULT_DATABASE_URL),
    ),
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="127.0.0.1")
EMAIL_PORT = env.int("EMAIL_PORT", default=1025)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
