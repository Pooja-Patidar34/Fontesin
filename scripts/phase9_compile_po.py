#!/usr/bin/env python3
"""Phase 9: Compile .po → .mo using polib (Windows-safe fallback when msgfmt absent)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("en", "de", "es", "fr")
DOMAINS = ("django", "djangojs")


def compile_with_polib(po_path: Path) -> None:
    po = polib.pofile(str(po_path))
    mo_path = po_path.with_suffix(".mo")
    po.save_as_mofile(str(mo_path))


def compile_with_msgfmt(po_path: Path) -> bool:
    try:
        subprocess.run(
            ["msgfmt", "--check", "-o", str(po_path.with_suffix(".mo")), str(po_path)],
            check=True,
            capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def main() -> int:
    use_msgfmt = compile_with_msgfmt.__doc__  # noqa — probe once
    has_msgfmt = False
    try:
        subprocess.run(["msgfmt", "--version"], check=True, capture_output=True)
        has_msgfmt = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    compiled = 0
    for locale in LOCALES:
        for domain in DOMAINS:
            po_path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            if not po_path.exists():
                continue
            if has_msgfmt:
                if not compile_with_msgfmt(po_path):
                    compile_with_polib(po_path)
            else:
                compile_with_polib(po_path)
            compiled += 1
            print(f"Compiled {po_path.relative_to(ROOT)}")

    print(f"Compiled {compiled} catalogs via {'msgfmt' if has_msgfmt else 'polib'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
