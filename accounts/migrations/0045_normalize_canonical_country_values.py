"""Normalize legacy country strings stored as translated UI labels.

Before the locale-invariance fix, coordinators could store target_region from
the active UI locale (e.g. "Allemagne" instead of "Germany"). Company.country
may also contain translated labels from imports or manual entry. This migration
rewrites known labels, aliases, and ISO codes to canonical English names.
"""

from django.db import migrations


def normalize_country_values(apps, schema_editor):
    from accounts.utils.country_matching import resolve_country_code

    from accounts.constants import COUNTRY_ENGLISH_NAMES

    User = apps.get_model("accounts", "User")
    Company = apps.get_model("accounts", "Company")

    for user in User.objects.exclude(target_region__isnull=True).exclude(target_region=""):
        raw = (user.target_region or "").strip()
        code = resolve_country_code(raw)
        if not code:
            continue
        canonical = COUNTRY_ENGLISH_NAMES.get(code, code)
        if canonical != raw:
            user.target_region = canonical
            user.save(update_fields=["target_region"])

    for company in Company.objects.exclude(country__isnull=True).exclude(country=""):
        raw = (company.country or "").strip()
        code = resolve_country_code(raw)
        if not code:
            continue
        # Keep ISO codes as-is; normalize names and translated labels to English.
        if len(raw) == 2 and raw.upper() == code:
            continue
        canonical = COUNTRY_ENGLISH_NAMES.get(code, code)
        if canonical.lower() != raw.lower():
            company.country = canonical
            company.save(update_fields=["country"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0044_align_preferred_language_choices"),
    ]

    operations = [
        migrations.RunPython(normalize_country_values, noop_reverse),
    ]
