"""Stable gettext keys for CommercialPlan marketing copy.

Logical keys: ``billing.plan.{code}.name``, ``.tagline``, ``.best_for``,
``.feature.{n}`` — implemented as ``pgettext("billing.plan.{code}", msgid)``
with English seed text from ``0005_reseed_plans_mvp`` as msgids.
"""

from django.utils.translation import pgettext

PLAN_CODES = ("free", "basic", "pro", "global")

# Canonical English copy keyed by plan code (source: 0005_reseed_plans_mvp).
PLAN_CANONICAL = {
    "free": {
        "name": "Free Plan",
        "tagline": "Get started in your domicile country",
        "best_for": (
            "Companies exploring the platform within their domicile country "
            "before committing to a paid plan."
        ),
        "features": [
            {"text": "1 country only (domicile by default)", "included": True},
            {"text": "Account registration & login", "included": True},
            {"text": "Company profile creation", "included": True},
            {
                "text": "Basic public listing (name, industry, country/region/city)",
                "included": True,
            },
            {"text": "Edit own company profile", "included": True},
            {"text": "Company certification", "included": False},
            {"text": "Partnerships", "included": False},
            {"text": "Messaging", "included": False},
            {"text": "Saving selected databases", "included": False},
        ],
    },
    "basic": {
        "name": "Basic Plan",
        "tagline": "Full access in one selected country",
        "best_for": (
            "Companies operating in a single national market who need full "
            "visibility and services."
        ),
        "features": [
            {"text": "Everything in FREE", "included": True},
            {"text": "Full company profile visibility", "included": True},
            {"text": "Access to one selected country / local market", "included": True},
            {"text": "Company certification", "included": True},
            {"text": "Partnerships", "included": True},
            {"text": "Messaging", "included": True},
            {"text": "Saving selected databases", "included": True},
            {"text": "Visible & searchable within licensed scope", "included": True},
        ],
    },
    "pro": {
        "name": "Pro Plan",
        "tagline": "Full access across one selected region",
        "best_for": (
            "Companies operating across a regional market "
            "(e.g. Europe, North America, Asia)."
        ),
        "features": [
            {"text": "Everything in BASIC", "included": True},
            {"text": "Access to one selected region", "included": True},
            {"text": "Europe / North America / South America", "included": True},
            {"text": "Asia / Middle East / Australia & Oceania", "included": True},
            {"text": "Visible & searchable within regional scope", "included": True},
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
            {"text": "Global visibility", "included": True},
            {
                "text": "Searchable across all available countries / regions",
                "included": True,
            },
        ],
    },
}


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


def attach_plan_display_fields(plan) -> None:
    """Mutate a CommercialPlan instance with display_* attributes."""
    plan.display_name = localized_plan_name(plan)
    plan.display_tagline = localized_plan_tagline(plan)
    plan.display_best_for = localized_plan_best_for(plan)
    plan.display_features = localized_plan_features(plan)


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
