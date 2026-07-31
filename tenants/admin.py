"""Django admin for workspace debugging in dev."""
from django.contrib import admin

from tenants.models import Workspace, WorkspaceInvite, WorkspaceMembership


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "owner", "created_at")
    search_fields = ("name", "slug", "owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ("workspace", "user", "role", "created_at")
    search_fields = ("workspace__name", "user__email")
    list_filter = ("role",)


@admin.register(WorkspaceInvite)
class WorkspaceInviteAdmin(admin.ModelAdmin):
    list_display = ("workspace", "email", "role", "expires_at", "used_at", "created_at")
    search_fields = ("email", "workspace__name")
    readonly_fields = ("token_hash", "created_at")
