#!/usr/bin/env python3
"""Compile .po catalogs to .mo using polib (no GNU msgfmt required)."""
from __future__ import annotations

import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "de", "es", "fr")
DOMAINS = ("django", "djangojs")


def main() -> int:
    for locale in LOCALES:
        for domain in DOMAINS:
            po_path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            mo_path = po_path.with_suffix(".mo")
            if not po_path.exists():
                continue
            po = polib.pofile(str(po_path))
            po.save_as_mofile(str(mo_path))
            print(f"compiled {mo_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
