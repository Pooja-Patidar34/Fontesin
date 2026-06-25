#!/usr/bin/env python3
"""Merge Phase 6 users/billing/workflows strings into locale django.po catalogs."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"

PHASE6_GLOBS = [
    # M4 Users
    "templates/dashboard/users.html",
    "templates/dashboard/_users_panel.html",
    "templates/dashboard/assign_roles.html",
    "templates/dashboard/roles.html",
    "templates/dashboard/permissions.html",
    "templates/dashboard/business_users.html",
    "templates/dashboard/consultant_users.html",
    # M5 Billing
    "templates/dashboard/plans.html",
    "templates/dashboard/subscriptions.html",
    "templates/dashboard/payments.html",
    "templates/dashboard/_payments_panel.html",
    "templates/dashboard/commissions.html",
    "templates/dashboard/_commissions_panel.html",
    "templates/dashboard/_commission_invoice_modal.html",
    "templates/dashboard/invoices.html",
    "templates/dashboard/plan_history.html",
    "templates/profile/_plan_card.html",
    "billing/plan_i18n.py",
    "billing/views.py",
    # M7 Workflows
    "templates/dashboard/join_requests.html",
    "templates/dashboard/partnerships.html",
    "templates/dashboard/coordinator_requests.html",
    "templates/dashboard/applications.html",
]

TRANS_RE = re.compile(
    r'\{%\s*trans\s+"((?:\\.|[^"\\])*)"(?:\s+context\s+"([^"]*)")?\s*%\}'
)

TRANS_SINGLE_RE = re.compile(
    r"\{%\s*trans\s+'((?:\\.|[^'\\])*)'(?:\s+context\s+'([^']*)')?\s*%\}"
)

BLOCKTRANS_RE = re.compile(
    r"\{%\s*blocktrans(?:\s+[^%]*?context\s+\"([^\"]*)\")?[^%]*?%\}"
    r"(.*?)\{%\s*endblocktrans\s*%\}",
    re.DOTALL,
)

# Django ``blocktrans`` looks up ``%(var)s`` placeholders at runtime, not ``{{ var }}``.
VAR_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

PGETTEXT_RE = re.compile(
    r"""pgettext\(\s*["']([^"']+)["']\s*,\s*["']((?:\\.|[^"\\])*)["']\s*\)"""
)

MSGID_RE = re.compile(
    r"""(?:_\(|gettext\()\s*"""
    r"""(?P<q>['"]{3}|['"])"""
    r"""(?P<s>(?:\\.|(?!\1).)*)"""
    r"""\1""",
    re.DOTALL,
)


def unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")


def po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parse_po_keys(path: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    text = path.read_text(encoding="utf-8")
    ctx = ""
    for line in text.splitlines():
        if line.startswith("msgctxt "):
            m = re.match(r'msgctxt "(.*)"', line)
            ctx = m.group(1) if m else ""
        elif line.startswith("msgid "):
            m = re.match(r'msgid "(.*)"', line)
            if m and m.group(1):
                keys.add((ctx, unescape(m.group(1))))
            ctx = ""
    return keys


def format_entry(*, ref: str, msgctxt: str, msgid: str, msgstr: str, fuzzy: bool) -> str:
    lines = [f"#: {ref}"]
    if fuzzy:
        lines.append("#, fuzzy")
    if msgctxt:
        lines.append(f'msgctxt "{po_escape(msgctxt)}"')
    if "\n" in msgid:
        lines.append('msgid ""')
        for part in msgid.split("\n"):
            lines.append(f'"{po_escape(part)}\\n"')
    else:
        lines.append(f'msgid "{po_escape(msgid)}"')
    if "\n" in msgstr:
        lines.append('msgstr ""')
        for part in msgstr.split("\n"):
            lines.append(f'"{po_escape(part)}\\n"')
    else:
        lines.append(f'msgstr "{po_escape(msgstr)}"')
    return "\n".join(lines)


def normalize_blocktrans_msgid(body: str) -> str:
    return VAR_PLACEHOLDER_RE.sub(r"%(\1)s", body)


def extract_from_file(rel: str) -> list[tuple[str, str, str]]:
    path = ROOT / rel
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    out: list[tuple[str, str, str]] = []
    ref = f"phase6 {rel}"

    for m in TRANS_RE.finditer(text):
        msgid = unescape(m.group(1))
        ctx = unescape(m.group(2) or "")
        if msgid.strip():
            out.append((ref, ctx, msgid))

    for m in TRANS_SINGLE_RE.finditer(text):
        msgid = unescape(m.group(1))
        ctx = unescape(m.group(2) or "")
        if msgid.strip():
            out.append((ref, ctx, msgid))

    for m in BLOCKTRANS_RE.finditer(text):
        ctx = unescape(m.group(1) or "")
        body = normalize_blocktrans_msgid(m.group(2).strip())
        if body:
            out.append((ref, ctx, body))

    for m in PGETTEXT_RE.finditer(text):
        ctx = m.group(1)
        msgid = unescape(m.group(2))
        if msgid.strip():
            out.append((ref, ctx, msgid))

    for m in MSGID_RE.finditer(text):
        msgid = unescape(m.group("s"))
        if msgid.strip():
            out.append((ref, "", msgid))

    return out


def main() -> None:
    entries: dict[tuple[str, str], str] = {}
    for rel in PHASE6_GLOBS:
        for ref, ctx, msgid in extract_from_file(rel):
            entries[(ctx, msgid)] = ref

    print(f"extracted {len(entries)} unique (context, msgid) pairs from Phase 6 files")

    for loc in ("en", "de", "es", "fr"):
        po_path = LOCALE / loc / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            print(f"skip {po_path}")
            continue
        existing = parse_po_keys(po_path)
        additions = []
        for (ctx, msgid), ref in sorted(entries.items(), key=lambda x: (x[0][0], x[0][1])):
            if (ctx, msgid) in existing:
                continue
            msgstr = msgid if loc == "en" else ""
            additions.append(
                format_entry(
                    ref=ref,
                    msgctxt=ctx,
                    msgid=msgid,
                    msgstr=msgstr,
                    fuzzy=loc != "en",
                )
            )
        if additions:
            text = po_path.read_text(encoding="utf-8").rstrip() + "\n\n"
            text += "\n\n".join(additions) + "\n"
            po_path.write_text(text, encoding="utf-8")
            print(f"{loc}: +{len(additions)} entries")


if __name__ == "__main__":
    main()
