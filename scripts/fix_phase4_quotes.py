#!/usr/bin/env python3
"""Fix broken _('...')" syntax from wrap_phase4_i18n.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAT = re.compile(r'_\("([^"]*)"\)"')


def main():
    globs = [
        ROOT.glob("accounts/**/*.py"),
        ROOT.glob("accounts_api/**/*.py"),
        ROOT.glob("billing/**/*.py"),
    ]
    for gen in globs:
        for path in gen:
            text = path.read_text(encoding="utf-8")
            new = PAT.sub(r'_("\1")', text)
            if new != text:
                path.write_text(new, encoding="utf-8")
                print(f"fixed {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
