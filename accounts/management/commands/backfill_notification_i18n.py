"""
Give legacy Notification rows the i18n payload they were written without.

Notifications used to store only the finished sentence, translated once at write
time into whatever language the recipient preferred *back then*. Migration 0056
added title_i18n / body_i18n so the inbox re-renders through gettext on every
read and follows the language switcher — but only for rows written after it.
Everything older still falls back to its frozen text, which is why a French UI
can show a German notification.

This command recovers the msgid behind that frozen text and stores a payload, so
those rows start following the language switcher too.

How the recovery works
----------------------
Every catalog entry (in all four locales, plus the English msgids themselves)
becomes an anchored regex: the literal text is escaped and each `%(param)s`
placeholder turns into a capture group. Matching a frozen string against those
regexes recovers both the msgid and the parameter values that were interpolated
into it — which is exactly what a payload holds.

Bodies were assembled from several messages (a lead sentence, an optional
" by X" clause, a trailing period), so a whole-string match usually fails. The
matcher then walks the text left to right, taking the LONGEST catalog entry that
matches at the cursor, and keeps any text it cannot attribute as a literal part.
A literal renders as-is, exactly like today's fallback, so a partial recovery is
still strictly better than none.

Rows whose text matches nothing are left completely untouched.

    python manage.py backfill_notification_i18n --dry-run   # report only
    python manage.py backfill_notification_i18n
"""

import gettext
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Notification


# Placeholders are always the named form — see accounts.utils.i18n_messages.
_PLACEHOLDER = re.compile(r"%\\\((\w+)\\\)s")

# A parameter is a name, a company, an amount: never empty, never spanning the
# whole rest of the string if a literal follows it.
_PARAM_PATTERN = "(?P<{name}>.+?)"

# Below this, a match found *inside* a longer string is more likely a
# coincidence than a recovery ("." or "OK" would match half the catalog).
_MIN_LITERAL_CHARS = 12

# An isolated leftover run is matched whole, not as a substring, so a short
# clause like "by %(name)s" is safe to accept there.
_MIN_LITERAL_CHARS_ISOLATED = 3


class _Entry:
    """One catalog line, compiled into something we can match text against."""

    __slots__ = ("msgid", "ctx", "regex", "regex_stripped", "weight")

    def __init__(self, msgid, ctx, translated):
        self.msgid = msgid
        self.ctx = ctx
        self.regex = self._compile(translated)
        # Legacy rows were written when some translations had lost the leading
        # space their msgid carries (" by %(name)s" → "von %(name)s"). Their
        # frozen text therefore lacks a space the repaired catalog now has, so
        # isolated runs are matched against this edge-trimmed variant and the
        # msgid — with its space — is what gets stored.
        stripped = translated.strip()
        self.regex_stripped = (
            self._compile(stripped) if stripped != translated else self.regex
        )
        # Literal (non-placeholder) length: how much real evidence a match has.
        self.weight = len(_PLACEHOLDER.sub("", re.escape(stripped)))

    @staticmethod
    def _compile(text):
        # Escape everything, then re-open the placeholders as capture groups.
        seen = set()

        def _sub(match):
            name = match.group(1)
            if name in seen:
                # A repeated placeholder must match what the first one caught.
                return f"(?P={name})"
            seen.add(name)
            return _PARAM_PATTERN.format(name=name)

        return re.compile(_PLACEHOLDER.sub(_sub, re.escape(text)), re.DOTALL)


def _load_entries():
    """Every catalog entry in every locale, longest-literal first."""
    entries = []
    seen = set()
    locale_dirs = [str(p) for p in settings.LOCALE_PATHS]
    languages = [code for code, _name in settings.LANGUAGES]

    for locale_dir in locale_dirs:
        for lang in languages:
            try:
                catalog = gettext.translation(
                    "django", locale_dir, languages=[lang]
                )._catalog
            except OSError:
                continue
            for key, translated in catalog.items():
                if not isinstance(key, str) or not key or not translated:
                    continue
                # Context-qualified keys are "ctx\x04msgid".
                ctx, _, msgid = key.partition("\x04")
                if not msgid:
                    msgid, ctx = ctx, None
                for text in (translated, msgid):
                    dedupe = (msgid, ctx, text)
                    if dedupe in seen:
                        continue
                    seen.add(dedupe)
                    entries.append(_Entry(msgid, ctx, text))

    entries.sort(key=lambda e: e.weight, reverse=True)
    return entries


def _match_whole(text, entries, min_weight=_MIN_LITERAL_CHARS, stripped=False):
    """Recover a single message that accounts for the entire string."""
    for entry in entries:
        if entry.weight < min_weight:
            break
        regex = entry.regex_stripped if stripped else entry.regex
        match = regex.fullmatch(text)
        if match:
            return _part_for(entry, match)
    return None


def _part_for(entry, match):
    part = {"id": entry.msgid}
    if entry.ctx:
        part["ctx"] = entry.ctx
    params = match.groupdict()
    if params:
        part["params"] = {k: {"t": v} for k, v in params.items()}
    return part


def _match_sequence(text, entries):
    """Walk the text, attributing the longest catalog entry at each position.

    Returns a parts list, or None when nothing at all could be attributed.
    """
    parts = []
    cursor = 0
    literal_start = 0
    recovered_any = False

    while cursor < len(text):
        best = None
        for entry in entries:
            if entry.weight < _MIN_LITERAL_CHARS:
                break
            match = entry.regex.match(text, cursor)
            # A greedy `.+?` can stop early; require the match to be the whole
            # remainder or to end on a boundary we can continue from.
            if match and match.end() > cursor:
                if best is None or match.end() > best[1].end():
                    best = (entry, match)
        if best is None:
            cursor += 1
            continue

        entry, match = best
        if match.start() > literal_start:
            parts.extend(_leftover_parts(text[literal_start:match.start()], entries))
        parts.append(_part_for(entry, match))
        recovered_any = True
        cursor = literal_start = match.end()

    if not recovered_any:
        return None
    if literal_start < len(text):
        parts.extend(_leftover_parts(text[literal_start:], entries))
    return parts


def _leftover_parts(run, entries):
    """Attribute a run of text the main pass could not place.

    These are the short connective clauses the old writer glued on — " by X",
    a trailing period. Matched WHOLE (never as a substring) and with any
    surrounding whitespace held back as the separator, so a 4-character msgid
    like "by %(name)s" can be recovered here without the coincidental matches
    that accepting it mid-string would cause.
    """
    stripped = run.strip()
    if not stripped:
        return [{"t": run}]

    recovered = _match_whole(
        stripped, entries, _MIN_LITERAL_CHARS_ISOLATED, stripped=True
    )
    if not recovered:
        return [{"t": run}]

    leading = run[: len(run) - len(run.lstrip())]
    trailing = run[len(run.rstrip()):]
    # The old writer concatenated some clauses with no separator at all
    # ("approvedby Admin User"). Today's code emits sep=" " there, so restore
    # the space when the recovered clause starts lower-case and nothing
    # separated it — that is the sentence the row was always meant to be.
    # Skip it when the msgid carries its own leading space (" by %(name)s"),
    # or the two would compound into a double space.
    if not leading and stripped[:1].islower() and not recovered["id"][:1].isspace():
        leading = " "
    if leading:
        recovered["sep"] = leading

    parts = [recovered]
    if trailing:
        parts.append({"t": trailing})
    return parts


def recover_payload(text, entries):
    """Build a render_payload()-compatible payload for a frozen string."""
    text = (text or "").strip()
    if not text:
        return None
    whole = _match_whole(text, entries)
    if whole:
        return {"parts": [whole]}
    parts = _match_sequence(text, entries)
    return {"parts": parts} if parts else None


class Command(BaseCommand):
    help = "Recover i18n payloads for Notification rows written before migration 0056."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be recovered without writing anything.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Only process the N most recent legacy rows (0 = all).",
        )

    def handle(self, *args, **options):
        from accounts.utils.i18n_messages import render_payload
        from django.utils import translation

        entries = _load_entries()
        self.stdout.write(f"Loaded {len(entries)} catalog patterns.")

        qs = Notification.objects.filter(
            title_i18n__isnull=True
        ) | Notification.objects.filter(body_i18n__isnull=True)
        qs = qs.distinct().order_by("-created_at")
        if options["limit"]:
            qs = qs[: options["limit"]]

        rows = list(qs)
        self.stdout.write(f"{len(rows)} legacy notification(s) to inspect.")

        titles_done = bodies_done = 0
        titles_missed = bodies_missed = 0
        updates = []

        for note in rows:
            changed = []
            if note.title_i18n is None and note.title:
                payload = recover_payload(note.title, entries)
                if payload:
                    note.title_i18n = payload
                    changed.append("title_i18n")
                    titles_done += 1
                else:
                    titles_missed += 1
            if note.body_i18n is None and note.body:
                payload = recover_payload(note.body, entries)
                if payload:
                    note.body_i18n = payload
                    changed.append("body_i18n")
                    bodies_done += 1
                else:
                    bodies_missed += 1
            if changed:
                updates.append((note, changed))

        self.stdout.write(
            f"  titles: {titles_done} recovered, {titles_missed} unmatched\n"
            f"  bodies: {bodies_done} recovered, {bodies_missed} unmatched"
        )

        # Show a couple of before/after renders so a human can sanity-check the
        # recovery rather than trust the counts.
        for note, _changed in updates[:3]:
            self.stdout.write("")
            self.stdout.write(f"  frozen : {note.title!r}")
            for lang in ("en", "fr", "de"):
                with translation.override(lang):
                    self.stdout.write(
                        f"  {lang}     : {render_payload(note.title_i18n)!r}"
                    )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDry run — nothing written."))
            return

        with transaction.atomic():
            for note, changed in updates:
                note.save(update_fields=changed)

        self.stdout.write(
            self.style.SUCCESS(f"\nUpdated {len(updates)} notification(s).")
        )
