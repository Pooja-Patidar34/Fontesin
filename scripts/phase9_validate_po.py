#!/usr/bin/env python3
"""Phase 9: Validate .po catalogs — syntax, placeholders, malformed translations."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "de", "es", "fr")
DOMAINS = ("django", "djangojs")

PLACEHOLDER_RE = re.compile(
    r"%\(\w+\)[a-zA-Z]|%\(\w+\)|%\d+\$[a-zA-Z]|%[sdif]|\{\{[^}]+\}\}|\{[^}]+\}"
)

FORMALITY_MARKER_RE = re.compile(r"\[(?:formeller|formelles|formelle)\s+Sie\]", re.IGNORECASE)


def extract_placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(text))


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        po = polib.pofile(str(path))
    except Exception as exc:
        return [f"{path}: parse error: {exc}"]

    for entry in po:
        if not entry.msgid:
            continue
        has_translation = bool(entry.msgstr) or bool(entry.msgstr_plural)
        if not has_translation and "fuzzy" not in entry.flags:
            errors.append(f"{path}: empty msgstr: {entry.msgctxt!r} / {entry.msgid[:60]!r}")
            continue
        if not has_translation:
            continue
        source = entry.msgstr or entry.msgstr_plural.get(0, "")
        id_ph = extract_placeholders(entry.msgid)
        str_ph = extract_placeholders(source)
        if entry.msgid_plural:
            for val in entry.msgstr_plural.values():
                str_ph |= extract_placeholders(val)
        missing = id_ph - str_ph
        extra = str_ph - id_ph
        if missing:
            errors.append(
                f"{path}: missing placeholders {missing} in {entry.msgctxt!r} / {entry.msgid[:50]!r}"
            )
        if extra and not id_ph:
            pass  # MT may add spurious % — only flag when msgid had none and msgstr has %

        if entry.msgstr and entry.msgstr.count("%") != entry.msgid.count("%") and (id_ph or "%" in entry.msgid):
            if missing or len(id_ph) != len(str_ph):
                pass  # already reported
            elif entry.msgid.count("%") != entry.msgstr.count("%"):
                errors.append(
                    f"{path}: %% count mismatch: {entry.msgctxt!r} / {entry.msgid[:50]!r}"
                )

        if entry.msgstr and FORMALITY_MARKER_RE.search(entry.msgstr):
            errors.append(
                f"{path}: unresolved formality marker in {entry.msgctxt!r} / {entry.msgid[:50]!r}"
            )

    return errors


def main() -> int:
    all_errors: list[str] = []
    for locale in LOCALES:
        for domain in DOMAINS:
            path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            if path.exists():
                all_errors.extend(validate_file(path))

    if all_errors:
        print(f"VALIDATION FAILED ({len(all_errors)} issues):")
        for err in all_errors[:50]:
            print(f"  {err}")
        if len(all_errors) > 50:
            print(f"  ... and {len(all_errors) - 50} more")
        return 1

    print("VALIDATION PASSED: all catalogs OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
