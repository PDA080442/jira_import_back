# Generated manually for metadata models

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jira", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="JiraProjectMetadata",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("project_id", models.CharField(blank=True, default="", max_length=64)),
                ("project_name", models.CharField(blank=True, default="", max_length=255)),
                ("project_key", models.CharField(blank=True, default="", max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("syncing", "Syncing"),
                            ("fresh", "Fresh"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("fetched_at", models.DateTimeField(blank=True, null=True)),
                ("ttl_seconds", models.PositiveIntegerField(default=3600)),
                ("last_sync_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connection",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_metadata",
                        to="jira.jiraconnection",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["connection", "status"], name="jira_jirapr_connect_8371bd_idx"),
                    models.Index(fields=["fetched_at"], name="jira_jirapr_fetched_aee9e4_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="JiraIssueType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jira_id", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("hierarchy_level", models.IntegerField(blank=True, null=True)),
                ("is_subtask", models.BooleanField(default=False)),
                ("description", models.TextField(blank=True, default="")),
                ("icon_url", models.URLField(blank=True, default="", max_length=512)),
                (
                    "metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="issue_types",
                        to="jira.jiraprojectmetadata",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["metadata"], name="jira_jirais_metadat_c582f6_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("metadata", "jira_id"),
                        name="unique_jira_issue_type_per_metadata",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="JiraField",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jira_id", models.CharField(max_length=64)),
                ("key", models.CharField(max_length=255)),
                ("name", models.CharField(max_length=255)),
                ("is_custom", models.BooleanField(default=False)),
                ("schema_type", models.CharField(blank=True, default="", max_length=128)),
                ("is_required", models.BooleanField(default=False)),
                ("template_field_type", models.CharField(blank=True, default="text", max_length=64)),
                ("extra", models.JSONField(blank=True, default=dict)),
                (
                    "metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="jira.jiraprojectmetadata",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["metadata"], name="jira_jirafi_metadat_36923a_idx"),
                    models.Index(fields=["metadata", "is_custom"], name="jira_jirafi_metadat_825178_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("metadata", "key"),
                        name="unique_jira_field_key_per_metadata",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="JiraBoard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jira_board_id", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("board_type", models.CharField(blank=True, default="", max_length=32)),
                (
                    "metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="boards",
                        to="jira.jiraprojectmetadata",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["metadata"], name="jira_jirabo_metadat_05dfc5_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("metadata", "jira_board_id"),
                        name="unique_jira_board_per_metadata",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="JiraSprint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jira_sprint_id", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("state", models.CharField(blank=True, default="", max_length=32)),
                ("start_date", models.DateTimeField(blank=True, null=True)),
                ("end_date", models.DateTimeField(blank=True, null=True)),
                ("goal", models.TextField(blank=True, default="")),
                (
                    "board",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sprints",
                        to="jira.jiraboard",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["board"], name="jira_jirasp_board_i_158000_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("board", "jira_sprint_id"),
                        name="unique_jira_sprint_per_board",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="JiraMetadataItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("priority", "Priority"),
                            ("status", "Status"),
                            ("component", "Component"),
                            ("label", "Label"),
                        ],
                        max_length=16,
                    ),
                ),
                ("jira_id", models.CharField(max_length=64)),
                ("name", models.CharField(max_length=255)),
                ("extra", models.JSONField(blank=True, default=dict)),
                (
                    "metadata",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="jira.jiraprojectmetadata",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["metadata", "kind"], name="jira_jirame_metadat_e995e1_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("metadata", "kind", "jira_id"),
                        name="unique_jira_metadata_item_per_kind",
                    ),
                ],
            },
        ),
    ]
