from django.contrib import admin

from sources.models import SourceFile, SourceSheet


class SourceSheetInline(admin.TabularInline):
    model = SourceSheet
    extra = 0
    readonly_fields = ("id", "index", "name", "row_count", "column_count")


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "file_type", "status", "is_active", "size_bytes", "updated_at")
    list_filter = ("file_type", "status", "is_active")
    search_fields = ("name", "checksum")
    readonly_fields = ("id", "created_at", "updated_at", "parse_started_at", "parsed_at", "created_by")
    inlines = [SourceSheetInline]


@admin.register(SourceSheet)
class SourceSheetAdmin(admin.ModelAdmin):
    list_display = ("name", "source_file", "index", "row_count", "column_count")
    search_fields = ("name",)
