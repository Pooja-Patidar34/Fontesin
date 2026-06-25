#!/usr/bin/env python3
"""Apply standardized SaaS terminology and fix known translation defects."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import polib

from terminology_glossary import (
    GLOSSARY,
    PLAN_STRATEGY_MSGIDS,
    PLAN_SUBSCRIPTION_CONTEXTS,
    PLAN_SUBSCRIPTION_MSGIDS,
    PLURALS,
)

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("de", "es", "fr")
DOMAINS = ("django", "djangojs")

# (locale, msgctxt, msgid) -> preferred msgstr
OVERRIDES: dict[tuple[str, str, str], str] = {
    # --- Navigation: Home ---
    ("fr", "website", "Home"): "Accueil",
    ("fr", "auth.verify", "Home"): "Accueil",
    ("de", "website", "Home"): "Startseite",
    ("de", "auth.verify", "Home"): "Startseite",
    ("es", "website", "Home"): "Inicio",
    ("es", "auth.verify", "Home"): "Inicio",
    # --- Critical mistranslations ---
    ("es", "common", "Close"): "Cerrar",
    ("es", "website", "Close"): "Cerrar",
    ("es", "common", "Save"): "Guardar",
    ("es", "common", "Delete"): "Eliminar",
    ("fr", "common", "Save"): "Enregistrer",
    ("de", "common", "Cancel"): "Abbrechen",
    ("de", "auth.verify", "Cancel"): "Abbrechen",
    # --- Dashboard (DE literal "car dashboard" is wrong for SaaS) ---
    ("de", "nav", "Dashboard"): "Dashboard",
    ("de", "sidebar", "Dashboard"): "Dashboard",
    ("de", "dashboard", "Dashboard"): "Dashboard",
    ("de", "pwa", "Dashboard"): "Dashboard",
    # --- Billing / plans (FR: forfait for subscription tier) ---
    ("fr", "billing", "Plan"): "Forfait",
    ("fr", "billing", "Plan History"): "Historique du forfait",
    ("fr", "billing", "Plan Name"): "Nom du forfait",
    ("fr", "billing", "Plan Details"): "Détails du forfait",
    ("fr", "billing", "Plans"): "Forfaits",
    ("fr", "billing", "Upgrade Plan"): "Mettre à niveau le forfait",
    ("fr", "billing", "Plan & Period"): "Forfait et période",
    ("fr", "common", "Upgrade Plan"): "Mettre à niveau le forfait",
    ("fr", "dashboard", "Plan"): "Forfait",
    ("fr", "website", "Plan"): "Forfait",
    ("fr", "", "Plan"): "Forfait",
    ("fr", "sidebar", "Plans"): "Forfaits",
    # --- Company terminology ---
    ("de", "companies", "Company Name"): "Unternehmensname",
    ("de", "website", "Company Name"): "Unternehmensname",
    ("de", "companies", "Company Details"): "Unternehmensdetails",
    ("de", "companies", "Company Logo"): "Unternehmenslogo",
    ("de", "profile", "Company Logo"): "Unternehmenslogo",
    ("de", "companies", "Delete Company?"): "Unternehmen löschen?",
    ("de", "sidebar", "Company Database"): "Unternehmensdatenbank",
    ("de", "dashboard", "Company Database"): "Unternehmensdatenbank",
    ("de", "website", "Company Database"): "Unternehmensdatenbank",
    ("de", "users", "Search company…"): "Unternehmen suchen…",
    ("es", "auth.register", "Company"): "Empresa",
    ("es", "companies", "Company"): "Empresa",
    ("es", "", "Company"): "Empresa",
    ("es", "billing", "Company"): "Empresa",
    ("es", "workflows", "Company:"): "Empresa:",
    ("es", "companies", "Company Name"): "Nombre de la empresa",
    ("es", "website", "Company Name"): "Nombre de la empresa",
  # --- Basic Info (DE inconsistent) ---
    ("de", "profile", "Basic Info"): "Grundinformationen",
    ("de", "companies", "Basic Info"): "Grundinformationen",
    # --- Join requests (FR: unify adhésion) ---
    ("fr", "sidebar", "Join Requests"): "Demandes d'adhésion",
    ("fr", "workflows", "Join Requests"): "Demandes d'adhésion",
    ("fr", "workflows", "Join Requests :"): "Demandes d'adhésion :",
    # --- Product name: keep GLOBAL canonical ---
    ("fr", "website", "GLOBAL"): "GLOBAL",
    # --- Remove vs Delete ---
    ("fr", "dashboard", "Remove"): "Retirer",
    ("fr", "dashboard", "Remove this saved filter?"): "Retirer ce filtre enregistré ?",
    ("de", "dashboard", "Remove"): "Entfernen",
    ("es", "dashboard", "Remove"): "Quitar",
    # --- Role (ES untranslated) ---
    ("es", "", "Role"): "Rol",
    ("es", "billing", "Role"): "Rol",
    ("es", "users", "Role"): "Rol",
    ("es", "workflows", "Role"): "Rol",
    ("es", "profile", "Role"): "Rol",
    ("es", "website", "Role"): "Rol",
    ("es", "users", "Roles"): "Roles",
    # --- DE certification tooltip ---
    (
        "de",
        "users",
        "View %(first_name)s's certification + subscription statistics",
    ): "Zertifizierungs- und Abonnementstatistiken von %(first_name)s anzeigen",
    # --- djangojs plan labels (no msgctxt in catalog) ---
    ("fr", "", "Choose Plan"): "Choisir le forfait",
    ("fr", "", "Choose Your Plan"): "Choisissez votre forfait",
    ("fr", "", "Upgrade Your Plan"): "Mettre à niveau votre forfait",
    ("fr", "", "Plan Comparison"): "Comparaison des forfaits",
}

# Locale-wide msgstr phrase fixes (applied only when msgid is not a strategy-plan string).
MSGSTR_PHRASE_FIXES: dict[str, list[tuple[str, str]]] = {
    "fr": [
        (r"\ble plan\b", "le forfait"),
        (r"\bce plan\b", "ce forfait"),
        (r"\bdu plan\b", "du forfait"),
        (r"\bau plan\b", "au forfait"),
        (r"\bdes plans\b", "des forfaits"),
        (r"\bPlans d'abonnement\b", "Forfaits d'abonnement"),
        (r"\bPlan de mise à niveau\b", "Mise à niveau du forfait"),
        (r"\bPlan & Période\b", "Forfait et période"),
        (r"\bPlan &\b", "Forfait &"),
        (r"\bdu régime\b", "du forfait"),
        (r"\ble régime\b", "le forfait"),
        (r"\bNom du régime\b", "Nom du forfait"),
        (r"\bHistorique du régime\b", "Historique du forfait"),
    ],
    "de": [
        (r"\bFirma\b", "Unternehmen"),
        (r"\bFirmen\b", "Unternehmen"),
        (r"\bFirmennamen\b", "Unternehmensnamen"),
        (r"\bFirmendetails\b", "Unternehmensdetails"),
        (r"\bFirmenlogo\b", "Unternehmenslogo"),
        (r"\bFirmenverzeichnis\b", "Unternehmensverzeichnis"),
        (r"\bFirmenübersicht\b", "Unternehmensübersicht"),
        (r"\bFirmenregister\b", "Unternehmensregister"),
        (r"\bFirmeninhaber\b", "Unternehmensinhaber"),
        (r"\bFirmendatenbank\b", "Unternehmensdatenbank"),
        (r"\bFirmenname\b", "Unternehmensname"),
        (r"\bFirmennamenindex\b", "Unternehmensnamenindex"),
        (r"\bFirmendaten\b", "Unternehmensdaten"),
        (r"\bFirmenhausnummer\b", "Handelsregisternummer"),
    ],
    "es": [
        (r"\bCompañía\b", "Empresa"),
        (r"\bcompañía\b", "empresa"),
    ],
}

TEMPLATE_PH_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def normalize_placeholders(text: str) -> str:
    return TEMPLATE_PH_RE.sub(r"%(\1)s", text)


def is_subscription_plan_entry(entry: polib.POEntry) -> bool:
    ctxt = entry.msgctxt or ""
    msgid = entry.msgid or ""
    if msgid in PLAN_STRATEGY_MSGIDS:
        return False
    if "Planned" in msgid and msgid not in PLAN_SUBSCRIPTION_MSGIDS:
        return False
    if ctxt in PLAN_SUBSCRIPTION_CONTEXTS and (
        msgid in PLAN_SUBSCRIPTION_MSGIDS
        or msgid.startswith("Plan")
        or " plan" in msgid.lower()
        or msgid.endswith(" Plan")
    ):
        return True
    if msgid in PLAN_SUBSCRIPTION_MSGIDS:
        return True
    return False


def apply_glossary_defaults(entry: polib.POEntry, locale: str) -> bool:
    """Set canonical short labels from glossary when msgid matches exactly."""
    if not entry.msgid or entry.msgstr is None:
        return False
    ctxt = entry.msgctxt or ""
    msgid = entry.msgid

    mapping = {
        "Company": GLOSSARY["company"],
        "Subscription": GLOSSARY["subscription"],
        "Subscriptions": PLURALS["subscription"],
        "Role": GLOSSARY["role"],
        "Roles": PLURALS["role"],
        "Permissions": PLURALS["permission"],
        "Save": GLOSSARY["save"],
        "Delete": GLOSSARY["delete"],
        "Remove": GLOSSARY["remove"],
        "Cancel": GLOSSARY["cancel"],
        "Close": GLOSSARY["close"],
        "Active": GLOSSARY["active"],
        "Pending": GLOSSARY["pending"],
        "Approved": GLOSSARY["approved"],
        "Rejected": GLOSSARY["rejected"],
        "Dashboard": GLOSSARY["dashboard"],
        "Overview": GLOSSARY["overview"],
        "Home": GLOSSARY["home"],
        "Search": GLOSSARY["search"],
        "Filter": GLOSSARY["filter"],
        "Settings": GLOSSARY["settings"],
        "Profile": GLOSSARY["profile"],
        "Member": GLOSSARY["member"],
        "User": GLOSSARY["user"],
        "Users": PLURALS["user"],
    }

    if msgid == "Plan" and is_subscription_plan_entry(entry):
        preferred = GLOSSARY["plan"][locale]
        if entry.msgstr != preferred:
            entry.msgstr = preferred
            return True
        return False

    if msgid == "Plans" and ctxt in ("billing", "sidebar", ""):
        preferred = PLURALS["plan"][locale]
        if entry.msgstr != preferred:
            entry.msgstr = preferred
            return True
        return False

    if msgid in mapping:
        preferred = mapping[msgid].get(locale)
        if preferred and entry.msgstr != preferred:
            entry.msgstr = preferred
            return True
    return False


def apply_msgstr_phrase_fixes(entry: polib.POEntry, locale: str) -> bool:
    if not entry.msgstr or locale not in MSGSTR_PHRASE_FIXES:
        return False
    if entry.msgid in PLAN_STRATEGY_MSGIDS:
        return False

    msgid_lower = (entry.msgid or "").lower()
    text = entry.msgstr
    changed = False

    if locale == "fr":
        if "plan" not in text.lower() and "régime" not in text.lower():
            return False
        if "planned" in msgid_lower:
            return False
    elif locale == "de":
        if not (
            "company" in msgid_lower
            or "firma" in text.lower()
            or "firmen" in text.lower()
            or msgid_lower == "basic info"
        ):
            return False
    elif locale == "es":
        if "compañía" not in text.lower():
            return False

    for pattern, repl in MSGSTR_PHRASE_FIXES[locale]:
        new_text = re.sub(pattern, repl, text, flags=re.IGNORECASE if locale == "es" else 0)
        if new_text != text:
            text = new_text
            changed = True
    if changed:
        entry.msgstr = text
    return changed


def load_en_index(domain: str) -> dict[tuple[str, str], polib.POEntry]:
    path = ROOT / "locale" / "en" / "LC_MESSAGES" / f"{domain}.po"
    index: dict[tuple[str, str], polib.POEntry] = {}
    for entry in polib.pofile(str(path)):
        if entry.msgid:
            index[(entry.msgctxt or "", entry.msgid)] = entry
    return index


def apply_overrides(po: polib.POFile, locale: str) -> int:
    changed = 0
    for entry in po:
        if not entry.msgid:
            continue
        key = (locale, entry.msgctxt or "", entry.msgid)
        override = OVERRIDES.get(key)
        if override and entry.msgstr != override:
            entry.msgstr = override
            changed += 1
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
    return changed


def normalize_entry_placeholders(entry: polib.POEntry) -> bool:
    changed = False
    new_id = normalize_placeholders(entry.msgid)
    if new_id != entry.msgid:
        entry.msgid = new_id
        changed = True
    if entry.msgstr:
        new_str = normalize_placeholders(entry.msgstr)
        if new_str != entry.msgstr:
            entry.msgstr = new_str
            changed = True
    return changed


def align_msgids_from_en(po: polib.POFile, en_index: dict[tuple[str, str], polib.POEntry]) -> int:
    changed = 0
    for entry in list(po):
        if not entry.msgid or "{{" not in entry.msgid:
            continue
        ctxt = entry.msgctxt or ""
        normalized_id = normalize_placeholders(entry.msgid)
        en_entry = en_index.get((ctxt, normalized_id))
        if not en_entry:
            continue
        if entry.msgid != normalized_id:
            entry.msgid = normalized_id
            if entry.msgstr:
                entry.msgstr = normalize_placeholders(entry.msgstr)
            changed += 1
    return changed


def remove_fuzzy_on_translated(po: polib.POFile) -> int:
    n = 0
    for entry in po:
        if entry.msgid and entry.msgstr and "fuzzy" in entry.flags:
            entry.flags.remove("fuzzy")
            n += 1
    return n


def process_file(locale: str, domain: str) -> tuple[int, int, int, int, int, int]:
    path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
    if not path.exists():
        return 0, 0, 0, 0, 0, 0
    po = polib.pofile(str(path))
    en_index = load_en_index(domain)

    override_n = apply_overrides(po, locale)
    glossary_n = sum(apply_glossary_defaults(e, locale) for e in po if e.msgid)
    phrase_n = sum(apply_msgstr_phrase_fixes(e, locale) for e in po if e.msgid)
    placeholder_n = sum(normalize_entry_placeholders(e) for e in po if e.msgid)
    align_n = align_msgids_from_en(po, en_index)
    fuzzy_n = remove_fuzzy_on_translated(po)

    po.save(str(path))
    return override_n, glossary_n, phrase_n, placeholder_n, align_n, fuzzy_n


def main() -> int:
    totals = [0, 0, 0, 0, 0, 0]
    labels = ("overrides", "glossary", "phrase fixes", "placeholders", "alignments", "fuzzy cleared")
    for locale in LOCALES:
        for domain in DOMAINS:
            counts = process_file(locale, domain)
            if any(counts):
                parts = ", ".join(f"{n} {label}" for n, label in zip(counts, labels) if n)
                print(f"{locale}/{domain}: {parts}")
            for i, n in enumerate(counts):
                totals[i] += n
    print(
        "Done: "
        + ", ".join(f"{n} {label}" for n, label in zip(totals, labels))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
