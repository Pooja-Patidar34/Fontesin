#!/usr/bin/env python3
"""Wrap _fail_create_company string literals with gettext."""
import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "accounts/view/profile.py"
text = path.read_text(encoding="utf-8")

pat = re.compile(
    r'return _fail_create_company\((?!_\()("(?:[^"\\]|\\.)*")',
)


def repl(m: re.Match) -> str:
    return f'return _fail_create_company(_({m.group(1)})'


new = pat.sub(repl, text)
# Multi-line string starts
pat2 = re.compile(
    r'return _fail_create_company\(\n\s+("(?:[^"\\]|\\.)*")',
)
new = pat2.sub(lambda m: f'return _fail_create_company(\n                _({m.group(1)})', new)

if new != text:
    path.write_text(new, encoding="utf-8")
    print("profile.py updated")
else:
    print("no changes")
