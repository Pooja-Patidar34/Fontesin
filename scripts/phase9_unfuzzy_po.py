#!/usr/bin/env python3
"""Phase 9: Remove fuzzy flags from all filled entries."""
from __future__ import annotations

from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "de", "es", "fr")
DOMAINS = ("django", "djangojs")


def unfuzzy_file(path: Path) -> int:
    po = polib.pofile(str(path))
    changed = 0
    for entry in po:
        if entry.msgstr and "fuzzy" in entry.flags:
            entry.flags.remove("fuzzy")
            changed += 1
        if entry.msgid_plural and entry.msgstr_plural:
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
                changed += 1
    if changed:
        po.save(str(path))
    return changed


def main() -> None:
    total = 0
    for locale in LOCALES:
        for domain in DOMAINS:
            path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            if path.exists():
                n = unfuzzy_file(path)
                if n:
                    print(f"{path.relative_to(ROOT)}: unfuzzied {n}")
                total += n
    print(f"Total unfuzzied: {total}")


if __name__ == "__main__":
    main()
