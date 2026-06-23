#!/usr/bin/env python3
"""
Merge Phase 3 auth/onboarding/email strings into locale catalogs.
Run when GNU gettext (makemessages) is unavailable locally; CI still runs makemessages/compilemessages.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"
DATA = Path(__file__).with_name("phase3_auth_translations.json")


def po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def entry_key(msgctxt: str | None, msgid: str) -> tuple[str | None, str]:
    return (msgctxt, msgid)


def parse_po(path: Path) -> set[tuple[str | None, str]]:
    text = path.read_text(encoding="utf-8")
    keys: set[tuple[str | None, str]] = set()
    ctxt = None
    for block in re.split(r"\n\n+", text):
        m = re.search(r'^msgctxt "(.*)"$', block, re.M)
        if m:
            ctxt = m.group(1)
        else:
            ctxt = None
        m = re.search(r'^msgid "(.*)"$', block, re.M)
        if not m:
            continue
        msgid = m.group(1)
        if msgid == "":
            continue
        # Unescape simple sequences
        msgid = msgid.encode("utf-8").decode("unicode_escape") if "\\n" in msgid else msgid
        keys.add((ctxt, msgid))
    return keys


def format_entry(
    *,
    references: list[str],
    msgctxt: str | None,
    msgid: str,
    msgstr: str,
    fuzzy: bool = False,
) -> str:
    lines = []
    for ref in references:
        lines.append(f"#: {ref}")
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


def main() -> None:
    catalog = json.loads(DATA.read_text(encoding="utf-8"))
    locales = ["en", "de", "es", "fr"]

    for domain in ("django", "djangojs"):
        items = catalog.get(domain, [])
        for loc in locales:
            po_path = LOCALE / loc / "LC_MESSAGES" / f"{domain}.po"
            if not po_path.exists():
                print(f"skip missing {po_path}")
                continue
            existing = parse_po(po_path)
            additions = []
            for item in items:
                ctxt = item.get("context")
                msgid = item["msgid"]
                if entry_key(ctxt, msgid) in existing:
                    continue
                refs = item.get("references", ["phase3"])
                if loc == "en":
                    msgstr = msgid
                else:
                    msgstr = item.get("translations", {}).get(loc, "")
                additions.append(
                    format_entry(
                        references=refs,
                        msgctxt=ctxt,
                        msgid=msgid,
                        msgstr=msgstr,
                        fuzzy=bool(msgstr == "" and loc != "en"),
                    )
                )
            if additions:
                text = po_path.read_text(encoding="utf-8").rstrip() + "\n\n"
                text += "\n\n".join(additions) + "\n"
                po_path.write_text(text, encoding="utf-8")
                print(f"{po_path.name} [{loc}]: +{len(additions)} entries")


if __name__ == "__main__":
    main()
