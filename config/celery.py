import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("jira_import")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

import core.celery_hooks  # noqa: E402, F401
