#!/usr/bin/env python3
"""Fill empty German auth-related msgstr entries using Google Translate."""
from __future__ import annotations

import re
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
PO = ROOT / "locale" / "de" / "LC_MESSAGES" / "django.po"
JS_PO = ROOT / "locale" / "de" / "LC_MESSAGES" / "djangojs.po"

AUTH_MARKERS = (
    'msgctxt "auth.',
    "accounts/view/auth.py",
    "templates/auth/",
    'msgctxt "auth.email"',
    "templates/email/",
    "accounts/utils/mailer.py",
)


def should_translate(block: str) -> bool:
    if 'msgstr ""' not in block:
        return False
    return any(m in block for m in AUTH_MARKERS)


def unescape_po(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"')


def escape_po(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def fill_file(path: Path, tr: GoogleTranslator) -> int:
    parts = re.split(r"\n\n+", path.read_text(encoding="utf-8"))
    updated = 0
    new_parts = [parts[0]]
    for block in parts[1:]:
        if not should_translate(block):
            new_parts.append(block)
            continue
        m = re.search(r'^msgid "(.*)"$', block, re.M)
        if not m or not m.group(1):
            new_parts.append(block)
            continue
        msgid = unescape_po(m.group(1))
        try:
            de = tr.translate(msgid)
            time.sleep(0.08)
            block = re.sub(
                r'^msgstr ""$',
                f'msgstr "{escape_po(de)}"',
                block,
                count=1,
                flags=re.M,
            )
            updated += 1
        except Exception:
            pass
        new_parts.append(block)
    path.write_text("\n\n".join(new_parts).rstrip() + "\n", encoding="utf-8")
    return updated


def main() -> None:
    tr = GoogleTranslator(source="en", target="de")
    n1 = fill_file(PO, tr)
    n2 = fill_file(JS_PO, tr)
    print(f"Filled {n1} django + {n2} djangojs German entries")


if __name__ == "__main__":
    main()
