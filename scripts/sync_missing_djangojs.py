#!/usr/bin/env python3
"""Copy missing djangojs entries from en into fr/de/es with standard translations."""
from __future__ import annotations

import sys
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("fr", "de", "es")

TRANSLATIONS: dict[str, dict[str, str]] = {
    "fr": {
        "${{ price }} / month": "${{ price }} / mois",
        "${{ price }} / year": "${{ price }} / an",
        "Save ${{ amount }}": "Économisez ${{ amount }}",
        "Select {{ plan_name }} Plan": "Sélectionner le forfait {{ plan_name }}",
        "Your current plan: <strong>{{ plan_name }}</strong>": "Votre forfait actuel : <strong>{{ plan_name }}</strong>",
        "{{ plan_name }} Plan": "Forfait {{ plan_name }}",
        "{{ plan_name }} Plan — Full Details": "Forfait {{ plan_name }} — Détails complets",
        "≈ ${{ monthly }} / month": "≈ ${{ monthly }} / mois",
        "Converted from {{ source_amount }} {{ source_currency }} at rate 1 {{ source_currency }} = {{ rate }} {{ display_curr }}": "Converti de {{ source_amount }} {{ source_currency }} au taux de 1 {{ source_currency }} = {{ rate }} {{ display_curr }}",
    },
    "de": {
        "${{ price }} / month": "${{ price }} / Monat",
        "${{ price }} / year": "${{ price }} / Jahr",
        "Save ${{ amount }}": "Sparen Sie ${{ amount }}",
        "Select {{ plan_name }} Plan": "{{ plan_name }}-Plan auswählen",
        "Your current plan: <strong>{{ plan_name }}</strong>": "Ihr aktueller Plan: <strong>{{ plan_name }}</strong>",
        "{{ plan_name }} Plan": "{{ plan_name }}-Plan",
        "{{ plan_name }} Plan — Full Details": "{{ plan_name }}-Plan — Alle Details",
        "≈ ${{ monthly }} / month": "≈ ${{ monthly }} / Monat",
        "Converted from {{ source_amount }} {{ source_currency }} at rate 1 {{ source_currency }} = {{ rate }} {{ display_curr }}": "Umgerechnet von {{ source_amount }} {{ source_currency }} zum Kurs 1 {{ source_currency }} = {{ rate }} {{ display_curr }}",
    },
    "es": {
        "${{ price }} / month": "${{ price }} / mes",
        "${{ price }} / year": "${{ price }} / año",
        "Save ${{ amount }}": "Ahorre ${{ amount }}",
        "Select {{ plan_name }} Plan": "Seleccionar plan {{ plan_name }}",
        "Your current plan: <strong>{{ plan_name }}</strong>": "Su plan actual: <strong>{{ plan_name }}</strong>",
        "{{ plan_name }} Plan": "Plan {{ plan_name }}",
        "{{ plan_name }} Plan — Full Details": "Plan {{ plan_name }} — Detalles completos",
        "≈ ${{ monthly }} / month": "≈ ${{ monthly }} / mes",
        "Converted from {{ source_amount }} {{ source_currency }} at rate 1 {{ source_currency }} = {{ rate }} {{ display_curr }}": "Convertido de {{ source_amount }} {{ source_currency }} al tipo 1 {{ source_currency }} = {{ rate }} {{ display_curr }}",
    },
}


def main() -> int:
    en_path = ROOT / "locale" / "en" / "LC_MESSAGES" / "djangojs.po"
    en_po = polib.pofile(str(en_path))
    en_by_key = {(e.msgctxt or "", e.msgid): e for e in en_po if e.msgid}

    added_total = 0
    for locale in LOCALES:
        path = ROOT / "locale" / locale / "LC_MESSAGES" / "djangojs.po"
        po = polib.pofile(str(path))
        have = {(e.msgctxt or "", e.msgid) for e in po if e.msgid}
        added = 0
        for key, en_entry in en_by_key.items():
            if key in have:
                continue
            ctxt, msgid = key
            if ctxt != "website" or msgid not in TRANSLATIONS[locale]:
                continue
            entry = polib.POEntry(
                msgid=msgid,
                msgstr=TRANSLATIONS[locale][msgid],
                msgctxt=ctxt,
                occurrences=en_entry.occurrences,
            )
            po.append(entry)
            added += 1
        if added:
            po.save(str(path))
            print(f"{locale}: added {added} djangojs entries")
        added_total += added

    print(f"Total added: {added_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
