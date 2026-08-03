"""Add encoding/delimiter diagnostics fields to SourceFile."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sources", "0002_googlesheetsource_googlesheettab_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sourcefile",
            name="delimiter_override",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="encoding_confidence",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="encoding_override",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="sourcefile",
            name="warnings",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
