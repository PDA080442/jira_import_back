"""Add SourceSnapshot, SourceRefreshRun and active_snapshot FKs."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0004_source_presets"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SourceSnapshot",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[("file", "File (Excel/CSV)"), ("google", "Google Sheets")],
                        max_length=16,
                    ),
                ),
                ("source_id", models.UUIDField()),
                ("data", models.JSONField(blank=True, default=dict)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("sheet_count", models.PositiveIntegerField(default=0)),
                ("checksum", models.CharField(blank=True, default="", max_length=64)),
                ("is_active", models.BooleanField(default=False)),
                ("is_truncated", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_source_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_snapshots",
                        to="tenants.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SourceRefreshRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[("file", "File (Excel/CSV)"), ("google", "Google Sheets")],
                        max_length=16,
                    ),
                ),
                ("source_id", models.UUIDField()),
                (
                    "trigger",
                    models.CharField(
                        choices=[
                            ("parse", "Parse"),
                            ("reparse", "Reparse"),
                            ("google_refresh", "Google refresh"),
                            ("preset_apply", "Preset apply"),
                            ("manual", "Manual"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("truncated", "Truncated"),
                        ],
                        max_length=16,
                    ),
                ),
                ("from_where", models.CharField(blank=True, default="", max_length=64)),
                ("error_message", models.CharField(blank=True, default="", max_length=2000)),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("meta", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "snapshot",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="refresh_runs",
                        to="sources.sourcesnapshot",
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_refresh_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_refresh_runs",
                        to="tenants.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="active_snapshot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="active_for_source_files",
                to="sources.sourcesnapshot",
            ),
        ),
        migrations.AddField(
            model_name="googlesheetsource",
            name="active_snapshot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="active_for_google_sources",
                to="sources.sourcesnapshot",
            ),
        ),
        migrations.AddIndex(
            model_name="sourcesnapshot",
            index=models.Index(
                fields=["workspace", "source_type", "source_id"],
                name="sources_sou_workspa_snap_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sourcesnapshot",
            index=models.Index(
                fields=["source_type", "source_id", "is_active"],
                name="sources_sou_type_id_act_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sourcesnapshot",
            index=models.Index(fields=["created_at"], name="sources_sou_created_snap_idx"),
        ),
        migrations.AddIndex(
            model_name="sourcerefreshrun",
            index=models.Index(
                fields=["workspace", "source_type", "source_id", "-started_at"],
                name="sources_ref_workspa_hist_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="sourcerefreshrun",
            index=models.Index(fields=["snapshot"], name="sources_ref_snapsho_idx"),
        ),
    ]
