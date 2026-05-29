from django.apps import AppConfig


class TemplatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "templates"
    label = "import_templates"
    verbose_name = "Import Templates"
