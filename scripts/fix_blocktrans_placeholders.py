#!/usr/bin/env python3
"""Normalize blocktrans placeholders in django.po catalogs.

Django ``blocktrans`` resolves ``%(name)s`` at runtime; custom sync scripts that
store ``{{ name }}`` in msgids prevent lookups from matching.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"

VAR_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def normalize_placeholders(text: str) -> str:
    return VAR_PLACEHOLDER_RE.sub(r"%(\1)s", text)


def fix_po_file(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("msgid ") or line.startswith("msgstr "):
            block = [line]
            i += 1
            while i < len(lines) and lines[i].startswith('"'):
                block.append(lines[i])
                i += 1
            joined = "".join(block)
            normalized = normalize_placeholders(joined)
            if normalized != joined:
                changed += 1
                out.append(normalized)
                continue
            out.extend(block)
            continue
        out.append(line)
        i += 1
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def main() -> None:
    total = 0
    for po_path in sorted(LOCALE.glob("*/LC_MESSAGES/django.po")):
        n = fix_po_file(po_path)
        if n:
            print(f"{po_path.relative_to(ROOT)}: {n} placeholder blocks normalized")
            total += n
    print(f"done ({total} blocks updated)")


if __name__ == "__main__":
    main()
