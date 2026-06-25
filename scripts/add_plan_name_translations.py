#!/usr/bin/env python3
"""Add billing.plan.* name entries to django.po when missing."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"

PLAN_NAMES = {
    "free": "FREE",
    "basic": "BASIC",
    "pro": "PRO",
    "global": "GLOBAL",
}

# Optional non-English plan name overrides (msgid stays English).
PLAN_NAME_MSGSTR = {
    "de": {"FREE": "FREI"},
    "es": {"FREE": "GRATIS"},
    "fr": {"FREE": "GRATUIT"},
}


def has_entry(text: str, ctx: str, msgid: str) -> bool:
    needle = f'msgctxt "{ctx}"\nmsgid "{msgid}"'
    return needle in text


def main() -> None:
    for loc in ("en", "de", "es", "fr"):
        po_path = LOCALE / loc / "LC_MESSAGES" / "django.po"
        text = po_path.read_text(encoding="utf-8")
        additions = []
        for code, msgid in PLAN_NAMES.items():
            ctx = f"billing.plan.{code}"
            if has_entry(text, ctx, msgid):
                continue
            msgstr = msgid
            if loc != "en":
                msgstr = PLAN_NAME_MSGSTR.get(loc, {}).get(msgid, msgid)
            additions.append(
                f"#: phase6 billing/plan_i18n.py\n"
                f'msgctxt "{ctx}"\n'
                f'msgid "{msgid}"\n'
                f'msgstr "{msgstr}"\n'
            )
        if additions:
            text = text.rstrip() + "\n\n" + "\n".join(additions) + "\n"
            po_path.write_text(text, encoding="utf-8")
            print(f"{loc}: +{len(additions)} plan name entries")
        else:
            print(f"{loc}: plan name entries already present")


if __name__ == "__main__":
    main()
