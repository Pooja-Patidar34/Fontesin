#!/usr/bin/env python3
"""Audit UI terminology consistency across locale catalogs."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("en", "fr", "de", "es")
DOMAINS = ("django", "djangojs")

PROPER_NOUNS = frozenset(
    {
        "FREE",
        "BASIC",
        "PRO",
        "ENTERPRISE",
        "GLOBAL",
        "OK",
        "Email",
        "ID",
        "PDF",
        "CSV",
        "API",
        "URL",
        "NACE",
        "VAT",
        "IBAN",
        "BIC",
        "SWIFT",
        "FONTESIN",
        "AdminLTE",
    }
)

CONCEPTS = {
    "company": [
        "Company",
        "Company Name",
        "Company Details",
        "Company Database",
        "Company Logo",
        "Company:",
        "Company Health",
    ],
    "user": ["User", "Users", "User Details", "Business User", "Member"],
    "plan": ["Plan", "Plans", "Plan Details", "Plan History", "Plan Name", "Upgrade Plan"],
    "subscription": ["Subscription", "Subscriptions", "Subscription Pending Approval"],
    "dashboard": ["Dashboard", "Overview", "Home"],
    "search": ["Search", "Search…", "Search companies…", "Search company…"],
    "delete": ["Delete", "Delete Company?", "Delete User?", "Remove"],
    "save": ["Save", "Save Changes", "Update", "Updated"],
    "cancel": ["Cancel", "Close", "Cancel Request"],
    "notification": ["Notifications", "Notification", "Alert"],
    "join_request": ["Join Requests", "Join Requests :", "Membership Request"],
    "role": ["Role", "Roles", "Permission", "Permissions"],
}


def load_catalog() -> dict[str, dict[tuple[str, str], str]]:
    catalog: dict[str, dict[tuple[str, str], str]] = {lang: {} for lang in LANGS}
    for lang in LANGS:
        for domain in DOMAINS:
            path = ROOT / "locale" / lang / "LC_MESSAGES" / f"{domain}.po"
            if not path.exists():
                continue
            for entry in polib.pofile(str(path)):
                if entry.msgid:
                    catalog[lang][(entry.msgctxt or "", entry.msgid)] = entry.msgstr
    return catalog


def main() -> None:
    catalog = load_catalog()

    print("=== TERMINOLOGY BY CONCEPT ===")
    for concept, msgids in CONCEPTS.items():
        print(f"\n--- {concept.upper()} ---")
        for lang in ("fr", "de", "es"):
            translations: dict[str, list[str]] = defaultdict(list)
            for mid in msgids:
                for (ctxt, msgid), msgstr in catalog[lang].items():
                    if msgid == mid and msgstr:
                        translations[msgstr].append(f"{ctxt or '(no ctxt)'}|{msgid}")
            unique = list(translations.keys())
            if len(unique) > 1:
                print(f"  {lang} INCONSISTENT ({len(unique)} variants):")
                for t, sources in sorted(translations.items(), key=lambda x: -len(x[1])):
                    print(f'    "{t}" <- {sources[:4]}')

    print("\n=== SAME MSGID, DIFFERENT TRANSLATIONS (per language) ===")
    for lang in ("fr", "de", "es"):
        by_msgid: dict[str, set[str]] = defaultdict(set)
        for (ctxt, msgid), msgstr in catalog[lang].items():
            if msgstr:
                by_msgid[msgid].add(msgstr)
        dupes = {k: v for k, v in by_msgid.items() if len(v) > 1}
        print(f"{lang}: {len(dupes)} msgids with multiple translations")
        for k, v in sorted(dupes.items(), key=lambda x: -len(x[1]))[:25]:
            print(f"  {k!r}: {sorted(v)}")

    print("\n=== UNTRANSLATED (msgstr == English msgid) ===")
    for lang in ("fr", "de", "es"):
        untrans = []
        for (ctxt, msgid), msgstr in catalog[lang].items():
            en_val = catalog["en"].get((ctxt, msgid), "")
            if msgstr and msgid and msgstr == msgid and en_val == msgid:
                if msgid not in PROPER_NOUNS and not re.match(r"^[A-Z0-9_\-]+$", msgid):
                    untrans.append((ctxt, msgid))
        print(f"{lang}: {len(untrans)} possibly untranslated")
        for ctxt, msgid in untrans[:25]:
            print(f"  {ctxt!r} / {msgid[:80]}")

    print("\n=== EMPTY TRANSLATIONS ===")
    for lang in ("fr", "de", "es"):
        empty = [
            (ctxt, msgid)
            for (ctxt, msgid), msgstr in catalog[lang].items()
            if not msgstr and catalog["en"].get((ctxt, msgid))
        ]
        print(f"{lang}: {len(empty)} empty")
        for ctxt, msgid in empty[:20]:
            print(f"  {ctxt!r} / {msgid[:80]}")

    print("\n=== DELETE vs REMOVE (English contexts) ===")
    for lang in LANGS:
        for key, msgstr in sorted(catalog[lang].items()):
            ctxt, msgid = key
            if "delete" in msgid.lower() or "remove" in msgid.lower():
                if msgid in ("Delete", "Remove") or "?" in msgid:
                    print(f"  {lang} [{ctxt}] {msgid!r} -> {msgstr!r}")

    print("\n=== MEMBERSHIP vs JOIN REQUEST synonyms in translations ===")
    patterns = [
        "membership",
        "mitgliedschaft",
        "membresía",
        "adhésion",
        "join request",
        "demande d'adhésion",
        "demande d'accès",
        "beitrittsanfrage",
        "solicitud de acceso",
    ]
    for lang in ("fr", "de", "es"):
        print(f"\n{lang}:")
        for pat in patterns:
            hits = [
                (ctxt, msgid[:50], msgstr[:70])
                for (ctxt, msgid), msgstr in catalog[lang].items()
                if pat.lower() in msgstr.lower()
            ]
            if hits:
                print(f"  '{pat}': {len(hits)}")
                for h in hits[:3]:
                    print(f"    {h}")


if __name__ == "__main__":
    main()
