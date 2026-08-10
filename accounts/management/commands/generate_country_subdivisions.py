"""
Regenerate accounts/data/country_subdivisions.py from the ISO 3166-2 dataset.

This is a BUILD-TIME command, not a runtime one. It reads `pycountry` (a
development-only dependency — see requirements.txt) and writes a plain Python
module that is committed to the repo, so the app itself never imports pycountry
and production installs nothing extra.

    python manage.py generate_country_subdivisions

Only TOP-LEVEL subdivisions are emitted (`parent_code is None`): the states,
provinces, regions and prefectures a person would name as "my state", not the
districts and communes nested under them. France, for example, yields its 26
regions and collectivities rather than all 124 rows including departments.

The 19 curated markets in accounts.constants.CURATED_COUNTRY_STATES are NOT
overridden by this data. Their lists use the canonical ENGLISH spellings that
existing Company.state / User.state_region rows already hold ("Bavaria", not
"Bayern"), and ISO uses the local spelling — swapping them would silently
invalidate stored values and shrink every Basic-plan user's directory.
"""

from pathlib import Path
import re

from django.core.management.base import BaseCommand, CommandError


HEADER = '''"""
ISO 3166-2 top-level subdivisions per country — GENERATED FILE, DO NOT EDIT.

Regenerate with:

    python manage.py generate_country_subdivisions

Source: the `pycountry` package (ISO 3166-2). Only top-level subdivisions are
included — see accounts/management/commands/generate_country_subdivisions.py
for what that means and why the curated markets in
accounts.constants.CURATED_COUNTRY_STATES take precedence over this data.

Names are the ISO spellings, which are often the LOCAL ones ("Bayern", not
"Bavaria"). That is fine for the countries served from here: nothing was ever
stored for them, so the ISO spelling becomes the canonical one on first use.
"""

# {count} countries, {total} subdivisions.
COUNTRY_SUBDIVISIONS = {{
'''

# ISO names sometimes carry a bracketed alternative or the code itself, e.g.
# "Wales [Cymru GB-CYM]". The bracket is metadata, not part of the name.
_BRACKET_SUFFIX = re.compile(r"\s*\[[^\]]*\]\s*$")


class Command(BaseCommand):
    help = "Regenerate accounts/data/country_subdivisions.py from ISO 3166-2."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit non-zero if the committed file is out of date, without writing.",
        )

    def handle(self, *args, **options):
        try:
            import pycountry
        except ImportError:
            raise CommandError(
                "pycountry is not installed. It is a generation-time dependency:\n"
                "    pip install pycountry"
            )

        # Import here so a broken constants module can't stop the generator from
        # being *read* — and so the country list stays the single source of the
        # codes we emit.
        from accounts.constants import COUNTRY_CODES

        data = {}
        for code in sorted(COUNTRY_CODES):
            rows = pycountry.subdivisions.get(country_code=code) or []
            names = sorted(
                {
                    _BRACKET_SUFFIX.sub("", row.name).strip()
                    for row in rows
                    if not row.parent_code
                }
            )
            if names:
                data[code] = names

        total = sum(len(v) for v in data.values())
        body = HEADER.format(count=len(data), total=total)
        for code, names in data.items():
            body += f'    "{code}": [\n'
            for name in names:
                escaped = name.replace("\\", "\\\\").replace('"', '\\"')
                body += f'        "{escaped}",\n'
            body += "    ],\n"
        body += "}\n"

        out_dir = Path(__file__).resolve().parents[2] / "data"
        out_dir.mkdir(exist_ok=True)
        init_py = out_dir / "__init__.py"
        target = out_dir / "country_subdivisions.py"

        if options["check"]:
            current = target.read_text(encoding="utf-8") if target.exists() else ""
            if current != body:
                raise CommandError(
                    f"{target} is out of date — run "
                    "`python manage.py generate_country_subdivisions`."
                )
            self.stdout.write(self.style.SUCCESS(f"{target.name} is up to date."))
            return

        if not init_py.exists():
            init_py.write_text("", encoding="utf-8")
        target.write_text(body, encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {target} — {len(data)} countries, {total} subdivisions "
                f"({len(COUNTRY_CODES) - len(data)} countries have none in ISO 3166-2)."
            )
        )
