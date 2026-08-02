from django.contrib import admin

from jira.models import (
    JiraBoard,
    JiraConnection,
    JiraField,
    JiraGuide,
    JiraIssueType,
    JiraMetadataItem,
    JiraProjectMetadata,
    JiraSprint,
)


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


class JiraIssueTypeInline(admin.TabularInline):
    model = JiraIssueType
    extra = 0


class JiraFieldInline(admin.TabularInline):
    model = JiraField
    extra = 0


class JiraMetadataItemInline(admin.TabularInline):
    model = JiraMetadataItem
    extra = 0


@admin.register(JiraProjectMetadata)
class JiraProjectMetadataAdmin(admin.ModelAdmin):
    list_display = ("connection", "project_key", "status", "fetched_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("project_key", "project_name", "connection__name")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [JiraIssueTypeInline, JiraFieldInline, JiraMetadataItemInline]


@admin.register(JiraBoard)
class JiraBoardAdmin(admin.ModelAdmin):
    list_display = ("name", "board_type", "metadata", "jira_board_id")
    search_fields = ("name", "jira_board_id")


@admin.register(JiraSprint)
class JiraSprintAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "board", "jira_sprint_id")
    search_fields = ("name", "jira_sprint_id")


@admin.register(JiraGuide)
class JiraGuideAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "locale", "version", "is_published", "updated_at")
    list_filter = ("is_published", "locale")
    search_fields = ("slug", "title")
    readonly_fields = ("id", "created_at", "updated_at")
