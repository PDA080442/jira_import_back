from django.contrib import admin

from jira.models import JiraConnection


@admin.register(JiraConnection)
class JiraConnectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "project_key",
        "is_active",
        "last_test_status",
        "updated_at",
    )
    list_filter = ("is_active", "last_test_status")
    search_fields = ("name", "email", "project_key")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_test_at",
        "last_test_status",
        "last_test_error",
        "created_by",
    )
    exclude = ("api_token_encrypted",)
