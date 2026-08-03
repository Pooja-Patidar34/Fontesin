"""Rewrite `User.preferred_language` values left behind by the old choice list.

Migration 0010 offered eight languages (en, de, cs, fr, ar, ja, es, pt); 0044
narrowed the field to the four locales we actually ship translations for
(SupportedLocale.ALL). 0044 only altered the choices — Django does not touch
existing rows on an AlterField — so any user who picked Czech, Arabic,
Japanese or Portuguese still holds a code the app now treats as invalid.

Those rows aren't broken at read time (`effective_preferred_language` routes
through `normalize_locale`, which already falls back to English), but they are
invalid against the field's choices: a `full_clean()` rejects them, and the
profile form renders no selected option because the stored code isn't in the
dropdown. This rewrites them once so the stored value matches what the app
resolves it to.

The fallback rule is inlined rather than imported from
`FontEsin.middleware.locale.normalize_locale` — a migration must keep behaving
the same even if that helper's rules change later.
"""

from django.db import migrations


# Frozen copy of SupportedLocale.ALL as of this migration.
SUPPORTED = {"en", "de", "es", "fr"}
FALLBACK = "en"


def _resolve(code):
    """Frozen copy of normalize_locale: strip the region tag, else fall back."""
    base = str(code).split("-")[0].strip().lower()
    return base if base in SUPPORTED else FALLBACK


def backfill_legacy_languages(apps, schema_editor):
    User = apps.get_model("accounts", "User")

    # NULL and "" mean "never chose one" — auth.py fills those from the request
    # locale on next login, so leave them alone.
    stale = (
        User.objects.exclude(preferred_language__isnull=True)
        .exclude(preferred_language="")
        .exclude(preferred_language__in=sorted(SUPPORTED))
    )

    for code in stale.values_list("preferred_language", flat=True).distinct():
        User.objects.filter(preferred_language=code).update(
            preferred_language=_resolve(code)
        )


def noop(apps, schema_editor):
    """No reverse — the original codes aren't recoverable once collapsed to en."""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0056_notification_body_i18n_notification_title_i18n"),
    ]

    operations = [
        migrations.RunPython(backfill_legacy_languages, noop),
    ]
