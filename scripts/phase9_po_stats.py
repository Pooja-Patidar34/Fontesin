#!/usr/bin/env python3
"""Phase 9: Translation coverage statistics."""
from __future__ import annotations

from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "de", "es", "fr")
DOMAINS = ("django", "djangojs")


def main() -> None:
    print(f"{'Locale':<8} {'Domain':<10} {'Entries':>8} {'Filled':>8} {'Empty':>8} {'Fuzzy':>8} {'Coverage':>10}")
    print("-" * 62)
    for locale in LOCALES:
        for domain in DOMAINS:
            path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            if not path.exists():
                continue
            po = polib.pofile(str(path))
            entries = [e for e in po if e.msgid]
            empty = sum(1 for e in entries if not e.msgstr)
            fuzzy = sum(1 for e in entries if "fuzzy" in e.flags)
            filled = len(entries) - empty
            pct = 100 * filled / len(entries) if entries else 0
            print(
                f"{locale:<8} {domain:<10} {len(entries):>8} {filled:>8} {empty:>8} {fuzzy:>8} {pct:>9.1f}%"
            )


if __name__ == "__main__":
    main()
