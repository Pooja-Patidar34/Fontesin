#!/usr/bin/env python3
"""Refresh the `django` .po catalogs from the current source tree.

Why this exists instead of a plain ``manage.py makemessages``: on Windows the
extraction step emits a POT whose wrapped ``#:`` reference comments lose their
``#:`` prefix on continuation lines, so ``msguniq`` aborts with "syntax error"
and no catalog is ever updated. That is why franchise (and other newer) strings
were marked translatable in the templates yet stayed English in the UI — the
catalogs simply never learned about them.

This script drives the same gettext pipeline Django would, with the broken POT
repaired in between:

    makemessages --keep-pot   (failure after the POT is written is expected)
    repair reference comments
    msguniq                   -> locale/django.clean.pot
    msgmerge --no-fuzzy-matching + msgattrib --no-obsolete  -> per-locale .po

``--no-fuzzy-matching`` is deliberate: msgmerge's guesses for these strings were
wrong far more often than right (it paired "Master Franchise" with "Save
Franchise"), and a wrong-but-confident translation is worse than an empty one.
New entries therefore land empty and are filled by ``i18n_fill.py``.

The ``djangojs`` domain is intentionally left alone: most of its entries have no
extractable source (they were authored against inline template JS) and a
regeneration with --no-obsolete would delete them.

Usage:
    python scripts/i18n_refresh.py            # refresh de/es/fr/en
    python scripts/i18n_refresh.py --stats    # report only, no writes
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_DIR = ROOT / "locale"
LOCALES = ("de", "es", "fr", "en")
POT = LOCALE_DIR / "django.pot"
MSG_POT = LOCALE_DIR / "django.msgclass.pot"
CLEAN_POT = LOCALE_DIR / "django.clean.pot"

# Notification text is authored as ``Msg("…", param=…)`` objects (see
# accounts/utils/i18n_messages.py) so it can be re-translated on read. xgettext
# has no idea that's a translation call and Django's makemessages offers no way
# to add a keyword, so those msgids are extracted in a second pass and merged.
MSG_KEYWORDS = ("Msg:1",)
SKIP_DIRS = {".git", "__pycache__", "migrations", "node_modules",
             "staticfiles", "htmlcov", "media", "logs"}


def run(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", **kw)


def python_exe() -> str:
    """Prefer the project venv so Django settings import the same way as usual."""
    candidates = [
        ROOT.parent / "fontesin_env" / "Scripts" / "python.exe",
        ROOT.parent / "fontesin_env" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def build_pot() -> None:
    """Extract messages. makemessages exits non-zero on the malformed POT; the
    POT itself is complete by then, which is all we need."""
    if POT.exists():
        POT.unlink()
    run(
        [python_exe(), "manage.py", "makemessages", "-l", LOCALES[0],
         "--keep-pot", "--no-obsolete"],
        cwd=ROOT,
    )
    if not POT.exists():
        raise SystemExit("makemessages produced no locale/django.pot")


def python_sources() -> list[Path]:
    """Project .py files worth scanning for Msg() calls."""
    found = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts):
            continue
        found.append(path)
    return sorted(found)


def build_msg_pot() -> None:
    """Second extraction pass for the Msg() notification messages."""
    if MSG_POT.exists():
        MSG_POT.unlink()
    listing = LOCALE_DIR / "msgclass.files"
    listing.write_text(
        "\n".join(str(p.relative_to(ROOT)).replace("\\", "/") for p in python_sources()),
        encoding="utf-8", newline="\n",
    )
    # An empty --keyword clears xgettext's defaults so this pass contributes
    # only the Msg() strings; everything else already came from makemessages.
    result = run(
        ["xgettext", "--language=Python", "--from-code=UTF-8", "--keyword",
         *[f"--keyword={kw}" for kw in MSG_KEYWORDS],
         f"--files-from={listing.relative_to(ROOT)}",
         "-o", str(MSG_POT.relative_to(ROOT))],
        cwd=ROOT,
    )
    listing.unlink()
    if result.returncode != 0:
        raise SystemExit(f"xgettext (Msg pass) failed:\n{result.stderr}")
    if not MSG_POT.exists():  # no Msg() call anywhere — nothing to merge
        return
    # xgettext leaves a CHARSET placeholder that msgcat refuses to merge.
    MSG_POT.write_text(
        MSG_POT.read_text(encoding="utf-8").replace("charset=CHARSET", "charset=UTF-8"),
        encoding="utf-8", newline="\n",
    )


def repair_pot(path: Path) -> int:
    """Re-attach the '#:' prefix xgettext/Django dropped on wrapped ref lines."""
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").split("\n")
    # Nothing legitimate in a PO file starts with a single space except the
    # continuation of a wrapped string, which always opens with a quote.
    broken = [i for i, line in enumerate(lines) if re.match(r'^ [^\s"]', line)]
    if broken:
        for i in broken:
            lines[i] = "#:" + lines[i]
        path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return len(broken)


def dedupe_pot() -> None:
    sources = [str(POT)] + ([str(MSG_POT)] if MSG_POT.exists() else [])
    if len(sources) > 1:
        combined = LOCALE_DIR / "django.combined.pot"
        result = run(["msgcat", "--use-first", "--to-code=UTF-8",
                      "-o", str(combined), *sources])
        if result.returncode != 0:
            raise SystemExit(f"msgcat failed:\n{result.stderr}")
        sources = [str(combined)]
    result = run(["msguniq", "--to-code=UTF-8", "-o", str(CLEAN_POT), *sources])
    if result.returncode != 0:
        raise SystemExit(f"msguniq failed even after repair:\n{result.stderr}")


def po_path(locale: str) -> Path:
    return LOCALE_DIR / locale / "LC_MESSAGES" / "django.po"


def stats(path: Path) -> tuple[int, int, int]:
    """(total, untranslated, fuzzy) entry counts, header excluded."""
    def count(extra: list[str]) -> int:
        out = run(["msgattrib", *extra, str(path)]).stdout
        # Every entry has exactly one 'msgid' line at column 0; drop the header.
        n = len(re.findall(r"^msgid ", out, flags=re.M))
        return max(n - 1, 0) if n else 0

    return count([]), count(["--untranslated"]), count(["--fuzzy"])


def merge(locale: str) -> None:
    path = po_path(locale)
    merged = path.with_suffix(".po.merged")
    result = run(["msgmerge", "-q", "--no-fuzzy-matching", "--previous",
                  "-o", str(merged), str(path), str(CLEAN_POT)])
    if result.returncode != 0:
        raise SystemExit(f"msgmerge failed for {locale}:\n{result.stderr}")
    result = run(["msgattrib", "--no-obsolete", "-o", str(path), str(merged)])
    if result.returncode != 0:
        raise SystemExit(f"msgattrib failed for {locale}:\n{result.stderr}")
    merged.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true",
                        help="report catalog state without touching the .po files")
    args = parser.parse_args()

    if args.stats:
        for locale in LOCALES:
            total, untranslated, fuzzy = stats(po_path(locale))
            print(f"{locale}: {total} entries, {untranslated} untranslated, {fuzzy} fuzzy")
        return 0

    build_pot()
    build_msg_pot()
    repaired = repair_pot(POT) + repair_pot(MSG_POT)
    dedupe_pot()
    print(f"POT: {CLEAN_POT.name} ({repaired} reference lines repaired)")

    for locale in LOCALES:
        merge(locale)
        total, untranslated, fuzzy = stats(po_path(locale))
        print(f"{locale}: {total} entries, {untranslated} untranslated, {fuzzy} fuzzy")

    print("\nNext: python scripts/i18n_fill.py   then   manage.py compilemessages")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
