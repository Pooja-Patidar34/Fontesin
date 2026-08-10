"""Stable gettext keys for CommercialPlan marketing copy.

Logical keys: ``billing.plan.{code}.name``, ``.tagline``, ``.best_for``,
``.feature.{n}`` — implemented as ``pgettext("billing.plan.{code}", msgid)``
with English seed text from ``0005_reseed_plans_mvp`` as msgids.
"""

from django.utils.translation import pgettext

PLAN_CODES = ("free", "basic", "pro", "global")

# Canonical English copy keyed by plan code.
#
# These strings are the msgids: the display layer translates THESE and ignores
# whatever the CommercialPlan row holds, so they have to describe the reach the
# code actually enforces in billing.utils.get_user_geographic_scope. The ladder
# is one geographic step per tier —
#
#     Free   → your TOWN, company names only
#     Basic  → your STATE (your whole country when no state is on file)
#     Pro    → your CONTINENT, every supported country on it
#     Global → worldwide
#
# — and it superseded the original 0005 seed copy ("domicile country",
# "one selected region"), which described a country/region model the product no
# longer has. Migrations 0015 / 0016 / 0018 / 0020 realigned the database rows;
# this table is the same copy, and the two must be changed together.
PLAN_CANONICAL = {
    "free": {
        "name": "Free Plan",
        "tagline": "Explore companies in your town",
        "best_for": (
            "Companies exploring the platform within their own town — "
            "names only, no details. Upgrade for full visibility."
        ),
        "features": [
            {"text": "Your own town only", "included": True},
            {"text": "Company names only — no further details", "included": True},
            {"text": "Account registration & login", "included": True},
            {"text": "Company profile creation", "included": True},
            {"text": "Edit own company profile", "included": True},
            {"text": "Company certification", "included": False},
            {"text": "Partnerships", "included": False},
            {"text": "Messaging", "included": False},
            {"text": "Saving selected databases", "included": False},
        ],
    },
    "basic": {
        "name": "Basic Plan",
        "tagline": "Full access in your state",
        "best_for": (
            "Companies operating in a single state or region who need full "
            "visibility and services across it."
        ),
        "features": [
            {"text": "Everything in FREE", "included": True},
            {"text": "Your whole state or region", "included": True},
            {"text": "Full company profile visibility", "included": True},
            {"text": "Company certification", "included": True},
            {"text": "Partnerships", "included": True},
            {"text": "Messaging", "included": True},
            {"text": "Saving selected databases", "included": True},
            {"text": "Visible & searchable within licensed scope", "included": True},
        ],
    },
    "pro": {
        "name": "Pro Plan",
        "tagline": "Full access across your continent",
        "best_for": (
            "Companies operating across their continent who need full "
            "visibility and services beyond their own country."
        ),
        "features": [
            {"text": "Everything in BASIC", "included": True},
            {"text": "Your whole continent, every country on it", "included": True},
            {"text": "Europe / North America / South America", "included": True},
            {"text": "Africa / Asia / Australia & Oceania", "included": True},
            {"text": "Visible & searchable across the continent", "included": True},
        ],
    },
    "global": {
        "name": "Global Plan",
        "tagline": "Worldwide visibility & access",
        "best_for": (
            "Companies operating internationally who need worldwide "
            "visibility and search."
        ),
        "features": [
            {"text": "Everything in PRO", "included": True},
            {"text": "Every country, worldwide", "included": True},
            {
                "text": "Searchable across all available countries / regions",
                "included": True,
            },
        ],
    },
}


# Comparison-table cell values. The table renders CommercialPlan.comparison,
# a free-text JSON blob, so its strings need a translation route of their own —
# they are not part of any plan's tagline/feature copy. Values not listed here
# fall through untranslated rather than being dropped.
# Marketing badges shown above a plan card, seeded by 0003 / 0005 as an emoji
# followed by the phrase. Only the words are translated.
BADGE_MSGIDS = ("Most Popular", "Best Value")

_BADGE_PREFIXES = {"⭐": "Most Popular", "\U0001f30d": "Best Value"}
_BADGE_PHRASES = frozenset(BADGE_MSGIDS)


COMPARISON_VALUE_MSGIDS = (
    "Limited",
    "Full",
    "Your town",
    "Your state",
    "Your continent",
    "Worldwide",
    "All countries / regions",
    # Values the older seeds wrote; kept so a database that has not run the
    # realignment migration still renders in the viewer's language.
    "Domicile country",
    "Selected country",
    "Selected region",
    "1 country",
    "1 region",
)


def _plan_context(code: str) -> str:
    return f"billing.plan.{(code or '').lower()}"


def _canonical(code: str) -> dict:
    return PLAN_CANONICAL.get((code or "").lower(), {})


def _localized_plan_field(plan, field: str) -> str:
    """Translate one canonical plan field, falling back to the stored value.

    The three public helpers below differ only in which field they read, so the
    lookup lives here once — otherwise a fix to one (say, the non-canonical
    fallback) silently leaves the other two behind.

    A canonical plan's text is translated under a per-plan context; a plan whose
    code isn't in PLAN_CANONICAL keeps whatever the DB holds, untranslated."""
    code = (getattr(plan, "code", None) or "").lower()
    msgid = _canonical(code).get(field) or getattr(plan, field, "") or ""
    if not msgid:
        return ""
    if code in PLAN_CANONICAL:
        return pgettext(_plan_context(code), msgid)
    return msgid


def localized_plan_name(plan) -> str:
    return _localized_plan_field(plan, "name")


def localized_plan_tagline(plan) -> str:
    return _localized_plan_field(plan, "tagline")


def localized_plan_best_for(plan) -> str:
    return _localized_plan_field(plan, "best_for")


def _feature_entry(raw):
    if isinstance(raw, dict):
        return raw.get("included", True), raw.get("text", "") or ""
    return True, str(raw)


def localized_plan_features(plan) -> list[dict]:
    """Return plan features with translated ``text`` and preserved ``included``."""
    code = (getattr(plan, "code", None) or "").lower()
    ctx = _plan_context(code)
    seed_features = _canonical(code).get("features", [])
    raw_features = getattr(plan, "features", None) or []
    out = []
    for i, raw in enumerate(raw_features):
        included, text = _feature_entry(raw)
        seed = seed_features[i] if i < len(seed_features) else None
        seed_text = seed["text"] if seed else None
        if code in PLAN_CANONICAL and seed_text and text == seed_text:
            translated = pgettext(ctx, seed_text)
        else:
            translated = text
        out.append({"included": included, "text": translated})
    return out


def localized_plan_badge(plan) -> str:
    """Translate the marketing badge above a plan card.

    ``badge_text`` is a free-text DB column seeded with an emoji + phrase
    ("⭐ Most Popular"). The emoji is split off and re-attached around the
    translation so the catalog holds words, not pictograms — and so a badge a
    deployment typed by hand still renders, untranslated, instead of vanishing.
    """
    raw = (getattr(plan, "badge_text", None) or "").strip()
    if not raw:
        return ""
    for emoji, phrase in _BADGE_PREFIXES.items():
        if raw == f"{emoji} {phrase}":
            return f"{emoji} {pgettext('billing.plan.badge', phrase)}"
    if raw in _BADGE_PHRASES:
        return pgettext("billing.plan.badge", raw)
    return raw


def localized_plan_comparison(plan) -> dict:
    """Comparison-table values with their text cells translated.

    Booleans pass through untouched — the template renders them as a tick or a
    cross, which needs no language. Only the free-text cells go through the
    catalog, and an unrecognised one is returned as-is so a hand-edited plan
    row still displays instead of blanking the column."""
    raw = getattr(plan, "comparison", None) or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if isinstance(value, str) and value in _COMPARISON_VALUES:
            out[key] = pgettext("billing.plan.comparison", value)
        else:
            out[key] = value
    return out


_COMPARISON_VALUES = frozenset(COMPARISON_VALUE_MSGIDS)


def attach_plan_display_fields(plan) -> None:
    """Mutate a CommercialPlan instance with display_* attributes."""
    plan.display_name = localized_plan_name(plan)
    plan.display_tagline = localized_plan_tagline(plan)
    plan.display_best_for = localized_plan_best_for(plan)
    plan.display_features = localized_plan_features(plan)
    plan.display_comparison = localized_plan_comparison(plan)
    plan.display_badge = localized_plan_badge(plan)


_SUBSCRIPTION_STATUS_MSGIDS = {
    "created": "Pending",
    "trial": "Trial",
    "active": "Active",
    "past_due": "Past Due",
    "suspended": "Suspended",
    "cancelled": "Cancelled",
}


def localized_subscription_status(subscription) -> str:
    """Translated subscription status label (``billing`` context)."""
    code = (getattr(subscription, "status", None) or "").lower()
    msgid = _SUBSCRIPTION_STATUS_MSGIDS.get(code)
    if msgid:
        return pgettext("billing", msgid)
    display = getattr(subscription, "get_status_display", None)
    return display() if callable(display) else code


def _plan_gettext_catalog():  # pragma: no cover
    """Anchor literals so makemessages / sync_phase6_po extract plan copy."""
    pgettext("billing.plan.free", "Free Plan")
    pgettext("billing.plan.basic", "Basic Plan")
    pgettext("billing.plan.pro", "Pro Plan")
    pgettext("billing.plan.global", "Global Plan")
    for code in PLAN_CODES:
        ctx = _plan_context(code)
        data = PLAN_CANONICAL[code]
        pgettext(ctx, data["tagline"])
        pgettext(ctx, data["best_for"])
        for feature in data["features"]:
            pgettext(ctx, feature["text"])
    for value in COMPARISON_VALUE_MSGIDS:
        pgettext("billing.plan.comparison", value)
    for badge in BADGE_MSGIDS:
        pgettext("billing.plan.badge", badge)


def pending_upgrade_access_note(current_plan_name: str) -> str:
    template = pgettext(
        "billing",
        "Awaiting admin approval. Until then you keep your current %(current_plan)s access.",
    )
    return template % {"current_plan": current_plan_name}


def deactivated_plan_message(plan_name: str) -> str:
    template = pgettext(
        "billing",
        "Your %(plan_name)s was deactivated by the admin.",
    )
    return template % {"plan_name": plan_name}
