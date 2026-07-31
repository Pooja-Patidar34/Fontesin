"""Deferred, catalog-backed messages for content stored in the database.

A Notification row used to keep only the finished sentence, translated once at
write time in whatever language the recipient preferred *back then*. Switching
the language afterwards left the inbox stuck in the old one, because a plain
CharField has no way back to the catalog entry it came from.

This module keeps the ingredients instead of the cake: the ``msgid``, its
context, and the interpolation parameters. They serialize to JSON, sit next to
the frozen text in the model, and get run through ``gettext`` again every time
the row is rendered — so the inbox follows the language switcher.

Authoring::

    title = Msg("New %(level)s request", level=level_label)
    body = MsgSeq(Msg("%(name)s has requested a %(level)s.", name=who, level=lvl))
    body.line(Msg("Territory: %(territory)s.", territory=territory))

Parameters may be plain strings (names, amounts — never translated), other
``Msg`` objects, or ``gettext_lazy`` proxies from ``accounts.constants``, whose
msgid is recovered so choice labels translate at render time too.

Rendering::

    render_payload(payload)   # in whatever language is currently active
"""

import logging

from django.utils.translation import gettext, pgettext


logger = logging.getLogger("technical")


# ── Authoring ───────────────────────────────────────────────────────────

class Msg:
    """One translatable sentence: a msgid, optional context, and params."""

    __slots__ = ("msgid", "ctx", "params")

    def __init__(self, msgid, ctx=None, **params):
        self.msgid = msgid
        self.ctx = ctx
        self.params = params

    def __str__(self):
        """Render in the currently active language (fallback / email use)."""
        return render_payload(self.to_payload())

    def to_payload(self):
        return {"parts": [_part(self)]}


class MsgSeq:
    """An ordered run of messages and literals joined into one block of text.

    Bodies are assembled piecewise — a lead sentence, an optional " by X"
    clause, a trailing period, extra lines — so each piece carries the
    separator that precedes it rather than being glued together up front.
    """

    def __init__(self, *items):
        self._parts = []
        for item in items:
            self.add(item)

    def add(self, item, sep=""):
        """Append `item` directly after what's there (no separator by default)."""
        if item is None:
            return self
        self._parts.append(_part(item, sep))
        return self

    def line(self, item):
        """Append `item` on a new line."""
        return self.add(item, sep="\n")

    def blank_line(self, item=""):
        """Append `item` after a blank line."""
        return self.add(item, sep="\n\n")

    def __len__(self):
        return len(self._parts)

    def __str__(self):
        return render_payload(self.to_payload())

    def to_payload(self):
        return {"parts": list(self._parts)}


# ── Serialization ───────────────────────────────────────────────────────

def _lazy_parts(value):
    """Recover ``(func_name, args)`` from a gettext_lazy/pgettext_lazy proxy.

    Django's lazy proxies expose their call signature through ``__reduce__``.
    Anything else — or a proxy shape we don't recognise — returns None and the
    caller falls back to the evaluated string.
    """
    reduce = getattr(value, "__reduce__", None)
    if reduce is None or not hasattr(value, "_args"):
        return None
    try:
        func, args = reduce()[1][0], reduce()[1][1]
        return func.__name__, args
    except Exception:  # pragma: no cover - defensive, proxy internals
        return None


def _value_payload(value):
    """Serialize an interpolation parameter."""
    if isinstance(value, Msg):
        return _part(value)
    if isinstance(value, MsgSeq):
        return value.to_payload()
    lazy = _lazy_parts(value)
    if lazy:
        name, args = lazy
        if name == "gettext" and len(args) == 1:
            return {"id": args[0]}
        if name == "pgettext" and len(args) == 2:
            return {"id": args[1], "ctx": args[0]}
    return {"t": str(value)}


def _part(item, sep=""):
    """Serialize one element of a sequence (a Msg, a lazy label, or a literal)."""
    part = {}
    if sep:
        part["sep"] = sep
    if isinstance(item, Msg):
        part["id"] = item.msgid
        if item.ctx:
            part["ctx"] = item.ctx
        if item.params:
            part["params"] = {k: _value_payload(v) for k, v in item.params.items()}
        return part
    part.update(_value_payload(item))
    return part


def to_payload(value):
    """Serialize a Msg/MsgSeq to a JSON-safe dict, or None for plain text.

    Plain strings are left to the caller's frozen column: they carry no msgid,
    so there is nothing to re-translate.
    """
    if isinstance(value, (Msg, MsgSeq)):
        return value.to_payload()
    return None


# ── Rendering ───────────────────────────────────────────────────────────

def _render_part(part):
    text = part.get("t")
    if text is not None:
        return text
    if "parts" in part:  # a nested sequence used as a parameter
        return "".join(p.get("sep", "") + _render_part(p) for p in part["parts"])
    msgid = part.get("id")
    if not msgid:
        return ""
    ctx = part.get("ctx")
    out = pgettext(ctx, msgid) if ctx else gettext(msgid)
    params = part.get("params")
    if params:
        out = out % {k: _render_part(v) for k, v in params.items()}
    return out


def render_payload(payload):
    """Render a stored payload in the currently active language.

    Returns "" for anything unusable — a malformed payload must never take the
    inbox down; the caller falls back to the frozen text column.
    """
    if not payload:
        return ""
    parts = payload.get("parts") if isinstance(payload, dict) else None
    if not parts:
        return ""
    try:
        return "".join(part.get("sep", "") + _render_part(part) for part in parts)
    except Exception as e:
        logger.error("render_payload(): failed to render %r: %s", payload, e)
        return ""
