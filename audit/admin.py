from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "trace_id", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("trace_id", "entity_id", "action")
    readonly_fields = (
        "id",
        "trace_id",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "payload_snapshot",
        "created_at",
    )
