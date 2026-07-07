#!/usr/bin/env python3
"""Remove fuzzy flags from auth-related po entries so translations apply at runtime."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKERS = ('msgctxt "auth.', "templates/auth/", "templates/email/", "accounts/view/auth.py", "accounts/utils/mailer.py")


def unfuzzy_file(path: Path) -> int:
    blocks = re.split(r"\n\n+", path.read_text(encoding="utf-8"))
    changed = 0
    out = []
    for block in blocks:
        if "#, fuzzy" in block and any(m in block for m in MARKERS):
            block = re.sub(r"#, fuzzy\n", "", block)
            changed += 1
        out.append(block)
    path.write_text("\n\n".join(out).rstrip() + "\n", encoding="utf-8")
    return changed


def main() -> None:
    for loc in ("en", "de", "es", "fr"):
        for domain in ("django", "djangojs"):
            path = ROOT / "locale" / loc / "LC_MESSAGES" / f"{domain}.po"
            if path.exists():
                n = unfuzzy_file(path)
                if n:
                    print(f"{path.relative_to(ROOT)}: unfuzzied {n}")


if __name__ == "__main__":
    main()
