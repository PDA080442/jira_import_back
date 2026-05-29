from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False

_INSECURE_SECRET = "django-insecure-change-me-in-production"
if not SECRET_KEY or SECRET_KEY == _INSECURE_SECRET:  # noqa: F405
    raise ImproperlyConfigured("Set a strong SECRET_KEY environment variable for production.")

if not env("DATABASE_URL", default=None):  # noqa: F405
    raise ImproperlyConfigured("DATABASE_URL environment variable is required for production.")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")  # noqa: F405
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS environment variable is required for production.")

DATABASES = {
    "default": configure_database(env("DATABASE_URL")),  # noqa: F405
}

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)  # noqa: F405
