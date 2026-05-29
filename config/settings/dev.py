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
