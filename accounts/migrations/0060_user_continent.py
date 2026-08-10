from django.db import migrations, models

from accounts.constants import CONTINENT_COUNTRIES


def backfill_continent(apps, schema_editor):
    """
    Every existing account already has a country, and a country belongs to
    exactly one continent (accounts.constants.CONTINENT_COUNTRIES) — so the new
    field can be filled without asking anyone to re-pick it. Accounts with no
    country (or an unrecognised free-text one) keep a NULL continent.
    """
    User = apps.get_model("accounts", "User")
    for continent, codes in CONTINENT_COUNTRIES.items():
        if not codes:
            continue
        User.objects.filter(country__in=codes).update(continent=continent)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0059_alter_franchiseapplication_created_franchise"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="continent",
            field=models.CharField(
                blank=True,
                choices=[
                    ("europe", "Europe"),
                    ("north_america", "North America"),
                    ("south_america", "South America"),
                    ("africa", "Africa"),
                    ("asia", "Asia"),
                    ("australia_oceania", "Australia / Oceania"),
                ],
                max_length=32,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_continent, migrations.RunPython.noop),
    ]
