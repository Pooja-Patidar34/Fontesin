#!/usr/bin/env python3
"""Phase 9: MT-fill empty msgstr for de/es/fr catalogs with placeholder preservation."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import polib
from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "scripts" / ".phase9_mt_cache.json"
LOCALES = ("de", "es", "fr")
DOMAINS = ("django", "djangojs")
BATCH_SIZE = 40

PH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"%\(\w+\)[a-zA-Z]"),
    re.compile(r"%\(\w+\)"),
    re.compile(r"%\d+\$[a-zA-Z]"),
    re.compile(r"%[sdif]"),
    re.compile(r"\{\{[^}]+\}\}"),
    re.compile(r"\{[^}]+\}"),
    re.compile(r"<[^>]+>"),
    re.compile(r"&#\d+;|&[a-z]+;"),
    re.compile(r"\\n"),
]

TOKEN = "⟦PH{0}⟧"


def cache_key(locale: str, entry: polib.POEntry) -> str:
    ctx = entry.msgctxt or ""
    return f"{locale}::{ctx}::{entry.msgid}"


def legacy_cache_key(locale: str, entry: polib.POEntry) -> str:
    return f"{locale}::{entry.msgid}"


def protect(text: str) -> tuple[str, list[str]]:
    placeholders: list[str] = []

    def sub(m: re.Match[str]) -> str:
        placeholders.append(m.group(0))
        return TOKEN.format(len(placeholders) - 1)

    out = text
    for pat in PH_PATTERNS:
        out = pat.sub(sub, out)
    return out, placeholders


def restore(text: str, placeholders: list[str]) -> str:
    for i, ph in enumerate(placeholders):
        text = text.replace(TOKEN.format(i), ph)
    return text


def translate_batch(
    texts: list[str],
    translator: GoogleTranslator,
) -> list[str]:
    if not texts:
        return []
    protected = [protect(t) for t in texts]
    batch = [p[0] for p in protected]
    for attempt in range(3):
        try:
            results = translator.translate_batch(batch)
            return [restore(r, protected[i][1]) for i, r in enumerate(results)]
        except Exception:
            time.sleep(2 * (attempt + 1))
    return texts


def save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def fill_po(path: Path, locale: str, cache: dict[str, str]) -> int:
    po = polib.pofile(str(path))
    translator = GoogleTranslator(source="en", target=locale)
    filled = 0

    pending: list[tuple[polib.POEntry, str]] = []
    for entry in po:
        if not entry.msgid:
            continue
        if entry.msgstr:
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            continue

        ck = cache_key(locale, entry)
        legacy = legacy_cache_key(locale, entry)
        translation = cache.get(ck) or cache.get(legacy)
        if translation:
            entry.msgstr = translation
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            filled += 1
        else:
            pending.append((entry, ck))

    for i in range(0, len(pending), BATCH_SIZE):
        chunk = pending[i : i + BATCH_SIZE]
        texts = [e.msgid for e, _ in chunk]
        results = translate_batch(texts, translator)
        for (entry, ck), translation in zip(chunk, results):
            if not translation:
                translation = entry.msgid
            entry.msgstr = translation
            cache[ck] = translation
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            filled += 1
        save_cache(cache)
        print(f"  {path.name}: {min(i + BATCH_SIZE, len(pending))}/{len(pending)}", flush=True)

    if filled:
        po.save(str(path))
    return filled


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locales", nargs="+", default=list(LOCALES))
    args = parser.parse_args()

    cache: dict[str, str] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    total_filled = 0
    for locale in args.locales:
        for domain in DOMAINS:
            path = ROOT / "locale" / locale / "LC_MESSAGES" / f"{domain}.po"
            if not path.exists():
                continue
            print(f"Filling {path.relative_to(ROOT)}...", flush=True)
            n = fill_po(path, locale, cache)
            print(f"  filled {n}", flush=True)
            total_filled += n

    save_cache(cache)
    print(f"Total filled: {total_filled}; cache size: {len(cache)}", flush=True)


if __name__ == "__main__":
    main()
