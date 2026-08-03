"""Add SourcePreset, PresetBinding and applied preset fields on sources."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0003_source_file_encoding_diagnostics"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SourcePreset",
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
                ("name", models.CharField(max_length=255)),
                ("description", models.CharField(blank=True, default="", max_length=2000)),
                (
                    "source_type",
                    models.CharField(
                        choices=[("file", "File (Excel/CSV)"), ("google", "Google Sheets")],
                        max_length=16,
                    ),
                ),
                ("settings", models.JSONField(blank=True, default=dict)),
                ("version", models.PositiveIntegerField(default=1)),
                ("last_applied_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_source_presets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="source_presets",
                        to="tenants.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PresetBinding",
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
                ("applied_version", models.PositiveIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("applied", "Applied"),
                            ("failed", "Failed"),
                            ("stale", "Stale"),
                        ],
                        default="applied",
                        max_length=16,
                    ),
                ),
                ("applied_settings", models.JSONField(blank=True, default=dict)),
                ("last_applied_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=2000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "applied_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preset_bindings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "preset",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bindings",
                        to="sources.sourcepreset",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preset_bindings",
                        to="tenants.workspace",
                    ),
                ),
            ],
            options={
                "ordering": ["-last_applied_at", "-updated_at"],
            },
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="applied_preset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applied_source_files",
                to="sources.sourcepreset",
            ),
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="applied_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="googlesheetsource",
            name="applied_preset",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applied_google_sources",
                to="sources.sourcepreset",
            ),
        ),
        migrations.AddField(
            model_name="googlesheetsource",
            name="applied_settings",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddIndex(
            model_name="sourcepreset",
            index=models.Index(fields=["workspace", "is_active"], name="sources_sou_workspa_idx"),
        ),
        migrations.AddIndex(
            model_name="sourcepreset",
            index=models.Index(
                fields=["workspace", "source_type"],
                name="sources_sou_workspa_type_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="sourcepreset",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("workspace", "source_type", "name"),
                name="unique_active_source_preset_name_per_workspace_type",
            ),
        ),
        migrations.AddIndex(
            model_name="presetbinding",
            index=models.Index(fields=["workspace", "preset"], name="sources_pre_workspa_preset_idx"),
        ),
        migrations.AddIndex(
            model_name="presetbinding",
            index=models.Index(
                fields=["workspace", "last_applied_at"],
                name="sources_pre_workspa_applied_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="presetbinding",
            constraint=models.UniqueConstraint(
                fields=("source_type", "source_id"),
                name="unique_preset_binding_per_source",
            ),
        ),
    ]
