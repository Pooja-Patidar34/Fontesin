#!/usr/bin/env python3
"""Extract Phase 4 gettext strings and merge into locale catalogs."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"

PHASE4_GLOBS = [
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
    "billing/utils.py",
    "accounts_api/view/companies.py",
    "accounts_api/view/profile.py",
    "accounts_api/serializers/company_serializers.py",
    "accounts/forms/company_form.py",
    "accounts/forms/tenant_form.py",
    "accounts/constants.py",
    "accounts/utils/notifications.py",
    "FontEsin/middleware/no_emoji.py",
    "FontEsin/i18n/__init__.py",
]

# Lightweight MT for smoke-test API strings (formal de)
MT = {
    "de": {
        "Authentication required": "Authentifizierung erforderlich",
        "Plan upgrade required": "Plan-Upgrade erforderlich",
        "This feature is not available on your current plan": "Diese Funktion ist in Ihrem aktuellen Plan nicht verfügbar",
        "Emojis are not allowed in input.": "Emojis sind in Eingaben nicht erlaubt.",
        "Invalid action.": "Ungültige Aktion.",
        "Permission denied": "Zugriff verweigert",
        "Company registry access requires Basic plan or higher. Please upgrade your plan.": "Der Firmenregister-Zugriff erfordert den Basic-Plan oder höher. Bitte upgraden Sie Ihren Plan.",
        "User not found": "Benutzer nicht gefunden",
        "All notifications marked as read.": "Alle Benachrichtigungen als gelesen markiert.",
        "Manufacturing": "Fertigung",
        "United States": "Vereinigte Staaten",
        "Germany": "Deutschland",
    },
    "es": {
        "Authentication required": "Autenticación requerida",
        "Plan upgrade required": "Se requiere actualización de plan",
        "Invalid action.": "Acción no válida.",
        "Permission denied": "Permiso denegado",
    },
    "fr": {
        "Authentication required": "Authentification requise",
        "Plan upgrade required": "Mise à niveau du forfait requise",
        "Invalid action.": "Action non valide.",
        "Permission denied": "Permission refusée",
    },
}

MSGID_RE = re.compile(
    r"""(?:_\(|_lazy\()\s*"""
    r"""(?P<q>['"]{3}|['"])"""
    r"""(?P<s>(?:\\.|(?!\1).)*)"""
    r"""\1""",
    re.DOTALL,
)


def po_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parse_po(path: Path) -> set[str]:
    keys: set[str] = set()
    for m in re.finditer(r'^msgid "(.*)"$', path.read_text(encoding="utf-8"), re.M):
        if m.group(1):
            keys.add(m.group(1))
    return keys


def format_entry(*, ref: str, msgid: str, msgstr: str, fuzzy: bool) -> str:
    lines = [f"#: {ref}"]
    if fuzzy:
        lines.append("#, fuzzy")
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


def extract_msgids() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for rel in PHASE4_GLOBS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        ids = set()
        for m in MSGID_RE.finditer(text):
            s = m.group("s")
            s = s.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")
            if s.strip():
                ids.add(s)
        if ids:
            found[rel] = ids
    return found


def main() -> None:
    extracted = extract_msgids()
    all_ids: set[str] = set()
    for ids in extracted.values():
        all_ids |= ids
    print(f"extracted {len(all_ids)} unique msgids from {len(extracted)} files")

    for loc in ("en", "de", "es", "fr"):
        po_path = LOCALE / loc / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            print(f"skip {po_path}")
            continue
        existing = parse_po(po_path)
        additions = []
        for msgid in sorted(all_ids):
            if msgid in existing:
                continue
            ref = "phase4"
            if loc == "en":
                msgstr = msgid
                fuzzy = False
            else:
                msgstr = MT.get(loc, {}).get(msgid, "")
                fuzzy = msgstr == ""
            additions.append(format_entry(ref=ref, msgid=msgid, msgstr=msgstr, fuzzy=fuzzy))
        if additions:
            text = po_path.read_text(encoding="utf-8").rstrip() + "\n\n"
            text += "\n\n".join(additions) + "\n"
            po_path.write_text(text, encoding="utf-8")
            print(f"{loc}: +{len(additions)} entries")


if __name__ == "__main__":
    main()
