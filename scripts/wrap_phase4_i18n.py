#!/usr/bin/env python3
"""Wrap user-facing strings in Phase 4 Python files with gettext."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GETTEXT_IMPORT = "from django.utils.translation import gettext as _\n"
LAZY_IMPORT = "from django.utils.translation import gettext_lazy as _\n"

# Files that need gettext (runtime)
RUNTIME_FILES = [
    "accounts/view/website.py",
    "accounts/view/join_request.py",
    "accounts/view/partnership.py",
    "accounts/view/company.py",
    "accounts/view/user.py",
    "accounts/view/profile.py",
    "accounts/view/tenant.py",
    "accounts/view/coordinator_request.py",
    "accounts/view/certification.py",
    "accounts/view/saved_filter.py",
    "accounts/view/application_review.py",
    "accounts/view/notification.py",
    "accounts/view/dashboard.py",
    "billing/views.py",
    "accounts_api/view/companies.py",
    "accounts_api/view/profile.py",
    "accounts_api/serializers/company_serializers.py",
    "accounts/forms/company_form.py",
    "accounts/forms/tenant_form.py",
]


def ensure_import(content: str, lazy: bool = False) -> str:
    imp = LAZY_IMPORT if lazy else GETTEXT_IMPORT
    if "from django.utils.translation import" in content:
        return content
    # Insert after last django import block
    lines = content.splitlines(keepends=True)
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith("from django.") or line.startswith("import django"):
            insert_at = i + 1
        elif insert_at and line.strip() and not line.startswith(("from ", "import ")):
            break
    if insert_at == 0:
        return imp + content
    lines.insert(insert_at, imp)
    return "".join(lines)


def wrap_quoted_strings(content: str) -> str:
    """Wrap common patterns that aren't already wrapped."""

    def wrap_msg(m: re.Match) -> str:
        prefix, quote, text, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        if text.startswith("%(") or "_(" in prefix:
            return m.group(0)
        # Skip very short / technical strings
        if not any(c.isalpha() for c in text):
            return m.group(0)
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'{prefix}_("{escaped}"){suffix}'

    patterns = [
        # messages.*
        (r'(messages\.(?:success|error|warning|info)\([^,]+,\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        # JsonResponse / Response message keys
        (r'(["\']message["\']\s*:\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        (r'(["\']error["\']\s*:\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        # ValidationError simple strings
        (r'(ValidationError\(\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        (r'(forms\.ValidationError\(\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        (r'(serializers\.ValidationError\(\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
        (r'(raise forms\.ValidationError\(\s*)(["\'])([^"\']+)(["\'])', wrap_msg),
    ]

    for pattern, repl in patterns:
        content = re.sub(pattern, repl, content)
    return content


def process_file(rel_path: str, lazy: bool = False) -> bool:
    path = ROOT / rel_path
    if not path.exists():
        print(f"SKIP missing: {rel_path}")
        return False
    original = path.read_text(encoding="utf-8")
    updated = ensure_import(original, lazy=lazy)
    updated = wrap_quoted_strings(updated)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        print(f"UPDATED: {rel_path}")
        return True
    print(f"UNCHANGED: {rel_path}")
    return False


def main() -> int:
    changed = 0
    for rel in RUNTIME_FILES:
        lazy = rel.startswith("accounts/forms/")
        if process_file(rel, lazy=lazy):
            changed += 1
    print(f"\n{changed} files updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
