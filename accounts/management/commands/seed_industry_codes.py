"""Seed/refresh NACE Rev.2 and NAICS 2022 lookup tables.

Run after applying migration 0031. Drops nothing — uses
``update_or_create`` keyed on ``code`` so it's safe to re-run after a CSV
refresh.

Usage:

    python manage.py seed_industry_codes               # both systems
    python manage.py seed_industry_codes --system nace
    python manage.py seed_industry_codes --system naics
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import NaceCode, NaicsCode


# The Eurostat NACE CSV we receive is exported through Excel with extra
# empty trailing columns, leaving a run of `,` characters at the end of
# every line that csv.DictReader appends to the last column's value. This
# pattern strips that junk (and any whitespace) from the right side of a
# field without touching legitimate commas mid-text.
_TRAILING_JUNK_RE = re.compile(r"[\s,]+$")


def _clean_field(value: str) -> str:
    return _TRAILING_JUNK_RE.sub("", (value or "")).strip()


def _open_csv(path: Path) -> io.StringIO:
    """Read a CSV file with encoding auto-detection.

    Both source files we receive are exported through Excel:
      - The NACE file from Eurostat is UTF-8 (with the ä in the header
        already lost to a literal `?` during export, but the rest is
        clean UTF-8).
      - The NAICS file from the U.S. Census Bureau is cp1252-encoded
        because Excel-on-Windows auto-inserts em-dashes (byte 0x97 in
        cp1252, U+2014 in Unicode) into descriptions.

    The file is fully read once into memory and decoded with UTF-8-sig
    first; if that fails anywhere in the file we retry with cp1252,
    which is a strict superset of ASCII and decodes any byte sequence.

    Returning a StringIO lets ``csv.DictReader`` consume the already-
    decoded text, so the UnicodeDecodeError (which is otherwise raised
    lazily mid-iteration) is caught up front instead of crashing the
    middle of a transaction.
    """
    data_bytes = path.read_bytes()
    try:
        text = data_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data_bytes.decode("cp1252")
    return io.StringIO(text)


DATA_DIR = Path(__file__).resolve().parent / "data"
NAICS_PATH = DATA_DIR / "naics_2022.csv"
NACE_PATH = DATA_DIR / "nace_rev2.csv"


class Command(BaseCommand):
    help = (
        "Seed NACE Rev.2 and NAICS 2022 lookup tables from CSV files in "
        "accounts/management/commands/data/. See data/README.md for the "
        "expected file format."
    )

    # NACE codes encode hierarchy in their length: level 1 = 1 char (A),
    # level 2 = 3 chars (A01), level 3 = 4 chars (A011), level 4 = 5 chars
    # (A0111). The parent of a row is the prefix of the previous level.
    NACE_PARENT_LEN = {1: None, 2: 1, 3: 3, 4: 4}

    def add_arguments(self, parser):
        parser.add_argument(
            "--system",
            choices=["nace", "naics", "all"],
            default="all",
            help="Which classification to load (default: all)",
        )

    def handle(self, *args, **options):
        system = options["system"]
        any_loaded = False

        if system in ("nace", "all"):
            if NACE_PATH.exists():
                self.load_nace()
                any_loaded = True
            else:
                self.stdout.write(
                    self.style.WARNING(f"NACE file not found at {NACE_PATH} — skipping")
                )

        if system in ("naics", "all"):
            if NAICS_PATH.exists():
                self.load_naics()
                any_loaded = True
            else:
                self.stdout.write(
                    self.style.WARNING(f"NAICS file not found at {NAICS_PATH} — skipping")
                )

        if not any_loaded:
            self.stdout.write(
                self.style.ERROR(
                    "No CSV files found. See "
                    "accounts/management/commands/data/README.md for required filenames."
                )
            )

    # ------------------------------------------------------------------ NACE

    @transaction.atomic
    def load_nace(self):
        self.stdout.write("Loading NACE Rev.2 …")

        # The German source column header contains an umlaut. We detect the
        # column by prefix so it works whether the file is saved as UTF-8 or
        # cp1252 (Excel default on European Windows locales).
        records: dict[str, dict] = {}
        f = _open_csv(NACE_PATH)
        reader = csv.DictReader(f, delimiter=";")
        title_col = next(
            (c for c in (reader.fieldnames or []) if c and c.startswith("Titel")),
            None,
        )
        if title_col is None:
            raise RuntimeError(
                f"NACE file at {NACE_PATH} is missing the 'Titel/…' column. "
                f"Found headers: {reader.fieldnames!r}"
            )

        for row in reader:
            level_raw = _clean_field(row.get("Ebene"))
            code = _clean_field(row.get("EDV-Code"))
            sub = _clean_field(row.get("Ebene Erl."))
            text = _clean_field(row.get(title_col))

            if not level_raw or not code or not text:
                continue
            try:
                level = int(level_raw)
            except ValueError:
                continue
            if level not in self.NACE_PARENT_LEN:
                # Levels 5+ in the source file are description bullet
                # points that share a parent's EDV-Code, not separate
                # classification entries.
                continue

            rec = records.setdefault(
                code,
                {"level": level, "title": None, "desc_parts": []},
            )
            if sub == "000":
                rec["title"] = text
            else:
                rec["desc_parts"].append(text)

        created = updated = 0
        for code, rec in records.items():
            title = (rec["title"] or code)[:500]
            description = "\n".join(rec["desc_parts"]).strip() or None
            _, was_created = NaceCode.objects.update_or_create(
                code=code,
                defaults={
                    "title": title,
                    "description": description,
                    "level": rec["level"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Second pass: resolve parents now that every node exists.
        code_to_id = dict(NaceCode.objects.values_list("code", "id"))
        for code, rec in records.items():
            prefix_len = self.NACE_PARENT_LEN[rec["level"]]
            parent_id = None
            if prefix_len is not None:
                parent_id = code_to_id.get(code[:prefix_len])
            NaceCode.objects.filter(code=code).update(parent_id=parent_id)

        self.stdout.write(
            self.style.SUCCESS(f"NACE: {created} created, {updated} updated")
        )

    # ----------------------------------------------------------------- NAICS

    @transaction.atomic
    def load_naics(self):
        self.stdout.write("Loading NAICS 2022 …")

        f = _open_csv(NAICS_PATH)
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        code_col = next(
            (c for c in fieldnames if "NAICS" in c and "Code" in c),
            None,
        )
        title_col = next(
            (c for c in fieldnames if "NAICS" in c and "Title" in c),
            None,
        )
        desc_col = next(
            (c for c in fieldnames if (c or "").strip().lower() == "description"),
            None,
        )
        if not code_col or not title_col:
            raise RuntimeError(
                f"NAICS file at {NAICS_PATH} is missing required columns. "
                f"Found headers: {fieldnames!r}"
            )

        records: list[dict] = []
        for row in reader:
            code = (row.get(code_col) or "").strip()
            title = (row.get(title_col) or "").strip()
            desc = (row.get(desc_col) or "").strip() if desc_col else ""
            if not code or not title:
                continue

            if "-" in code:
                # Range codes (31-33, 44-45, 48-49) are top-level sectors.
                level = 2
            elif code.isdigit() and 2 <= len(code) <= 6:
                level = len(code)
            else:
                continue

            # The source marks subtotal rows (everything except 6-digit
            # leaves) with a trailing 'T' (e.g. "ManufacturingT",
            # "Other Services (except Public Administration)T"). Strip
            # it from non-leaf titles unconditionally — NAICS leaves
            # never legitimately end in a bare 'T' per the published spec.
            if level < 6 and title.endswith("T"):
                title = title[:-1].rstrip()

            records.append(
                {
                    "code": code,
                    "title": title,
                    "description": desc or None,
                    "level": level,
                }
            )

        created = updated = 0
        for rec in records:
            _, was_created = NaicsCode.objects.update_or_create(
                code=rec["code"],
                defaults={
                    "title": rec["title"][:500],
                    "description": rec["description"],
                    "level": rec["level"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Build lookups for parent resolution.
        code_to_id = dict(NaicsCode.objects.values_list("code", "id"))
        # Map each digit covered by a range code (e.g. '31', '32', '33' → '31-33')
        # so a 3-digit code like '311' can resolve up to its range parent.
        digit_to_range: dict[str, str] = {}
        for code in code_to_id:
            if "-" in code:
                start, _, end = code.partition("-")
                if start.isdigit() and end.isdigit():
                    for d in range(int(start), int(end) + 1):
                        digit_to_range[str(d)] = code

        def parent_code_for(code: str) -> Optional[str]:
            if "-" in code or len(code) == 2:
                return None
            prefix = code[:-1]
            if len(prefix) == 2 and prefix in digit_to_range:
                return digit_to_range[prefix]
            return prefix if prefix in code_to_id else None

        for rec in records:
            parent_code = parent_code_for(rec["code"])
            parent_id = code_to_id.get(parent_code) if parent_code else None
            NaicsCode.objects.filter(code=rec["code"]).update(parent_id=parent_id)

        self.stdout.write(
            self.style.SUCCESS(f"NAICS: {created} created, {updated} updated")
        )
