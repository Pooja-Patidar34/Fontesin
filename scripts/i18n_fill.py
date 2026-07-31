#!/usr/bin/env python3
"""Fill empty msgstr entries in the `django` catalogs from a reviewed JSON map.

Earlier phases MT-filled catalogs with deep_translator (see phase9_fill_po.py).
This one takes human-reviewed strings instead, so the franchise vocabulary stays
consistent with scripts/terminology_glossary.py.

Rather than editing .po text by hand, translations are emitted as a *supplement*
catalog and folded in with gettext's own tools, so quoting, wrapping and plural
layout are never our problem:

    supplement.po + django.po  --msgcat --use-first-->  msgmerge (order/refs)

Entries already translated in the .po win: msgcat --use-first is given the
supplement first, but the supplement only ever contains entries that were empty
at generation time, so nothing existing is overwritten.

The English catalog needs no translation map — an untranslated entry there is
filled with its own msgid.

Input:  scripts/i18n_translations.json  (list of {ctx, id, plural, de, es, fr})
        strings are stored exactly as they appear inside .po quotes, i.e. with
        \\" for a literal quote and %% for a literal percent.

Usage:
    python scripts/i18n_fill.py            # fill de/es/fr from the map, then en
    python scripts/i18n_fill.py --check     # report coverage, write nothing
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "locale"
CLEAN_POT = LOCALE_DIR / "django.clean.pot"
MAP_PATH = Path(__file__).resolve().parent / "i18n_translations.json"
TARGET_LOCALES = ("de", "es", "fr")


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")


def discard(path: Path) -> None:
    """Delete a scratch file, tolerating a Windows lock from an indexer/watcher —
    a leftover temp file must not fail a completed fill."""
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


def po_path(locale: str) -> Path:
    return LOCALE_DIR / locale / "LC_MESSAGES" / "django.po"


def parse_entries(text: str) -> list[dict]:
    """Split a .po into entries, keeping msgctxt/msgid/msgid_plural/msgstr as the
    raw (still escaped) strings that appear between the quotes."""
    entries = []
    for block in text.split("\n\n"):
        if "\nmsgid " not in "\n" + block:
            continue
        fields: dict[str, list[str]] = {}
        current = None
        for line in block.split("\n"):
            line = line.rstrip("\r")
            if line.startswith("#"):
                continue
            for key, prefix in (
                ("plural", "msgid_plural"),
                ("ctx", "msgctxt"),
                ("id", "msgid"),
                ("str", "msgstr"),
            ):
                if line.startswith(prefix):
                    current = key
                    fields.setdefault(key, []).append(line)
                    break
            else:
                if line.startswith('"') and current:
                    fields[current].append(line)

        def value(key: str) -> str | None:
            if key not in fields:
                return None
            parts = []
            for line in fields[key]:
                match = re.search(r'"((?:[^"\\]|\\.)*)"\s*$', line)
                if match:
                    parts.append(match.group(1))
            return "".join(parts)

        msgid = value("id")
        if not msgid:  # header, or a stray block
            continue
        entries.append(
            {
                "ctx": value("ctx"),
                "id": msgid,
                "plural": value("plural"),
                "str": value("str") or "",
            }
        )
    return entries


def key_of(entry: dict) -> str:
    return f"{entry['ctx'] or ''}\x04{entry['id']}"


def untranslated(locale: str) -> list[dict]:
    entries = parse_entries(po_path(locale).read_text(encoding="utf-8"))
    return [e for e in entries if not e["str"]]


def header_of(text: str) -> str:
    """The leading comment + empty-msgid block, verbatim."""
    head, _, _ = text.partition("\n\n")
    return head + "\n\n"


def write_supplement(locale: str, rows: list[dict], path: Path) -> int:
    lines = [header_of(po_path(locale).read_text(encoding="utf-8"))]
    written = 0
    for row in rows:
        translation = row.get(locale)
        if not translation:
            continue
        if row.get("ctx"):
            lines.append(f'msgctxt "{row["ctx"]}"\n')
        lines.append(f'msgid "{row["id"]}"\n')
        if row.get("plural"):
            forms = translation if isinstance(translation, list) else [translation, translation]
            lines.append(f'msgid_plural "{row["plural"]}"\n')
            for index, form in enumerate(forms):
                lines.append(f'msgstr[{index}] "{form}"\n')
        else:
            if isinstance(translation, list):
                raise SystemExit(f"plural translation for a singular entry: {row['id']!r}")
            lines.append(f'msgstr "{translation}"\n')
        lines.append("\n")
        written += 1
    path.write_text("".join(lines), encoding="utf-8", newline="\n")
    return written


def fold_in(locale: str, supplement: Path) -> None:
    target = po_path(locale)
    combined = target.with_suffix(".po.combined")
    result = run(["msgcat", "--use-first", "-o", str(combined),
                  str(supplement), str(target)])
    if result.returncode != 0:
        raise SystemExit(f"msgcat failed for {locale}:\n{result.stderr}")
    # Re-merge against the POT so entry order and #: references stay canonical.
    result = run(["msgmerge", "-q", "--no-fuzzy-matching", "-o", str(target),
                  str(combined), str(CLEAN_POT)])
    if result.returncode != 0:
        raise SystemExit(f"msgmerge failed for {locale}:\n{result.stderr}")
    discard(combined)


def fuzzy_entries(locale: str) -> list[dict]:
    out = run(["msgattrib", "--fuzzy", str(po_path(locale))])
    if out.returncode != 0:
        raise SystemExit(f"msgattrib --fuzzy failed for {locale}:\n{out.stderr}")
    return parse_entries(out.stdout)


def repair_fuzzy(locale: str, by_key: dict) -> int:
    """A fuzzy entry is ignored by gettext, so the UI shows English. These were
    fuzzy because the msgstr had lost or renamed a placeholder; the map carries
    corrected text, so overwrite and clear the flag."""
    pending = fuzzy_entries(locale)
    if not pending:
        return 0
    unmapped = [e for e in pending if key_of(e) not in by_key]
    if unmapped:
        for entry in unmapped:
            print(f"  FUZZY without a mapping [{entry['ctx'] or '-'}] {entry['id'][:80]}")
        raise SystemExit(f"{locale}: cannot repair fuzzy entries without translations")

    supplement = LOCALE_DIR / locale / "LC_MESSAGES" / "supplement.po"
    write_supplement(locale, [by_key[key_of(e)] for e in pending], supplement)
    target = po_path(locale)
    combined = target.with_suffix(".po.combined")
    result = run(["msgcat", "--use-first", "-o", str(combined), str(supplement), str(target)])
    if result.returncode != 0:
        raise SystemExit(f"msgcat failed for {locale}:\n{result.stderr}")
    # Every fuzzy entry has just been given reviewed text, so the flags can go.
    result = run(["msgattrib", "--clear-fuzzy", "-o", str(target), str(combined)])
    if result.returncode != 0:
        raise SystemExit(f"msgattrib --clear-fuzzy failed for {locale}:\n{result.stderr}")
    discard(combined)
    discard(supplement)
    return len(pending)


def fill_english() -> int:
    """English is the source language: an empty msgstr means 'same as msgid'."""
    rows = [{"ctx": e["ctx"], "id": e["id"], "plural": e["plural"],
             "en": [e["id"], e["plural"]] if e["plural"] else e["id"]}
            for e in untranslated("en")]
    supplement = LOCALE_DIR / "en" / "LC_MESSAGES" / "supplement.po"
    written = write_supplement("en", rows, supplement)
    fold_in("en", supplement)
    discard(supplement)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if not CLEAN_POT.exists():
        raise SystemExit(f"{CLEAN_POT} is missing — run scripts/i18n_refresh.py first")

    rows = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    by_key = {f"{r.get('ctx') or ''}\x04{r['id']}": r for r in rows}

    missing = [e for e in untranslated("de") if key_of(e) not in by_key]
    print(f"map: {len(rows)} entries; de untranslated without a mapping: {len(missing)}")
    for entry in missing[:20]:
        print(f"  MISSING [{entry['ctx'] or '-'}] {entry['id'][:90]}")
    if args.check:
        return 1 if missing else 0
    if missing:
        raise SystemExit("refusing to fill with an incomplete map")

    for locale in TARGET_LOCALES:
        pending = untranslated(locale)
        rows_for_locale = [by_key[key_of(e)] for e in pending if key_of(e) in by_key]
        supplement = LOCALE_DIR / locale / "LC_MESSAGES" / "supplement.po"
        written = write_supplement(locale, rows_for_locale, supplement)
        fold_in(locale, supplement)
        discard(supplement)
        repaired = repair_fuzzy(locale, by_key)
        print(f"{locale}: filled {written} entries, repaired {repaired} fuzzy, "
              f"{len(untranslated(locale))} still empty")

    written = fill_english()
    print(f"en: filled {written} entries from msgid, {len(untranslated('en'))} still empty")
    return 0


if __name__ == "__main__":
    sys.exit(main())
