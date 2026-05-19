import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0030_company_extra_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="NaceCode",
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
                ("code", models.CharField(max_length=20, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True, null=True)),
                ("level", models.PositiveSmallIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="accounts.nacecode",
                    ),
                ),
            ],
            options={
                "verbose_name": "NACE Code",
                "verbose_name_plural": "NACE Codes",
                "ordering": ["code"],
            },
        ),
        migrations.AddIndex(
            model_name="nacecode",
            index=models.Index(fields=["parent"], name="accounts_na_parent__nace_idx"),
        ),
        migrations.AddIndex(
            model_name="nacecode",
            index=models.Index(fields=["level"], name="accounts_na_level_nace_idx"),
        ),
        migrations.CreateModel(
            name="NaicsCode",
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
                ("code", models.CharField(max_length=20, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("description", models.TextField(blank=True, null=True)),
                ("level", models.PositiveSmallIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="accounts.naicscode",
                    ),
                ),
            ],
            options={
                "verbose_name": "NAICS Code",
                "verbose_name_plural": "NAICS Codes",
                "ordering": ["code"],
            },
        ),
        migrations.AddIndex(
            model_name="naicscode",
            index=models.Index(fields=["parent"], name="accounts_na_parent_naics_idx"),
        ),
        migrations.AddIndex(
            model_name="naicscode",
            index=models.Index(fields=["level"], name="accounts_na_level_naics_idx"),
        ),
        migrations.AddField(
            model_name="company",
            name="nace_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="companies",
                to="accounts.nacecode",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="naics_code",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="companies",
                to="accounts.naicscode",
            ),
        ),
    ]
