"""
Listings Engine - service layer.

Implements the ownership, role and visibility helpers described in the
MVP Phase 3 cookbook (Step 2 - Backend foundation) plus the audit-log writer
used by the create/update/suspend flows (Section 12).

The plan-scope visibility functions are intentionally MVP *placeholders*
(cookbook Step 2.9): they encode the "public / members / private" model that
`Listing.visibility_scope` currently uses and are the single place to swap in
real plan-tier logic on Day 9 without touching the views.
"""

import re

from django.db.models import Q

from accounts.constants import COUNTRY_ENGLISH_NAMES
from accounts.models import NaceCode
from listings.models import Listing, ListingAuditLog


# ---------------------------------------------------------------------------
# Role helpers
# ---------------------------------------------------------------------------
def _role_code(user):
    role = getattr(user, "role", None)
    return (getattr(role, "code", "") or "").lower()


def is_business_user(user):
    return _role_code(user) == "business_user"


def is_consultant(user):
    return _role_code(user) == "consultant"


def is_admin(user):
    """Master Admin per cookbook Section 19.6 (superuser or master_admin role)."""
    return bool(getattr(user, "is_superuser", False)) or _role_code(user) == "master_admin"


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------
def company_belongs_to_user(company, user):
    """A Business User may act on a company they own (owner_user).

    Superusers/admins bypass the check. Tenant boundary is always enforced.
    """
    if company is None:
        return False
    if is_admin(user):
        return True
    if getattr(user, "tenant_id", None) != company.tenant_id:
        return False
    return company.owner_user_id == user.id


def is_listing_owner(listing, user):
    return listing.owner_user_id == user.id


# ---------------------------------------------------------------------------
# Visibility placeholders (cookbook Step 2.9 - swap for plan logic on Day 9)
# ---------------------------------------------------------------------------
def get_user_visible_scopes(user):
    """Scopes a user is allowed to see in search.

    MVP: everyone can see public + members listings; a user additionally sees
    their own private ones (handled by the owner filter in the view).
    """
    return [Listing.PUBLIC, Listing.MEMBERS, Listing.PRIVATE]


def can_publish_to_scope(user, scope):
    """Whether the user may publish a listing into the given visibility scope.

    MVP placeholder: all authenticated Business Users may publish to any of the
    three scopes. Plan-tier restrictions land here on Day 9.
    """
    return scope in dict(Listing.VISIBILITY_CHOICES)


def can_view_scope(user, scope):
    """Whether the user may view/react to a listing in the given scope."""
    return scope in get_user_visible_scopes(user)


# ---------------------------------------------------------------------------
# Audit log (cookbook Section 11 / 12)
# ---------------------------------------------------------------------------
def create_audit_log(listing, action, old_value, new_value, changed_by):
    return ListingAuditLog.objects.create(
        listing=listing,
        action=action,
        old_value=old_value,
        new_value=new_value,
        changed_by=changed_by,
    )


# ---------------------------------------------------------------------------
# Browse / search filters (shared by the web page and the JSON API)
# ---------------------------------------------------------------------------
def nace_filter(raw):
    """Build the NACE/ISIC browse filter from whatever the box submitted.

    The picker submits a bare code ("A"), but the box is still a text input, so
    it can also arrive as the display string ("A — AGRICULTURE, FORESTRY AND
    FISHING", e.g. pasted from a listing's detail page) or as free-typed words.
    All three have to work; previously only a raw substring was tried, which
    matched nothing for the first two.

    Returns (Q, display_string_for_the_search_box).
    """
    raw = (raw or "").strip()
    # "CODE — Title" → "CODE". Both dash forms, since the em dash survives a
    # copy/paste but a hand-typed value usually uses a hyphen.
    head = re.split(r"\s+[—-]\s+", raw, maxsplit=1)[0].strip()

    code = NaceCode.objects.filter(code__iexact=head).first()
    if code:
        # A section or division means "everything underneath it". NACE codes are
        # prefix-structured (A → A01 → A0111), so the prefix IS the subtree.
        return Q(nace_code__code__istartswith=code.code), f"{code.code} — {code.title}"

    # Not a known code — treat it as a search term over code prefix and title.
    # startswith (not contains) on the code, so "A" doesn't drag in every code
    # that merely happens to contain the letter.
    return (
        Q(nace_code__code__istartswith=raw) | Q(nace_code__title__icontains=raw),
        raw,
    )


def country_code(raw):
    """Resolve whatever the country box submitted to its ISO code, if known.

    Returns "" when the value matches no known country, so the dropdown falls
    back to "All countries" rather than silently selecting the wrong entry.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.upper() in COUNTRY_ENGLISH_NAMES:
        return raw.upper()
    for iso, name in COUNTRY_ENGLISH_NAMES.items():
        if raw.lower() == name.lower():
            return iso
    return ""


def country_filter(raw):
    """Match the country box against how countries are actually stored.

    The create form's dropdown stores an ISO code ("IN"), so filtering on the
    English name ("India") found nothing. Accept either, and keep the substring
    match as a fallback for legacy rows that hold a free-typed name.
    """
    raw = (raw or "").strip()
    q = Q(country__iexact=raw) | Q(country__icontains=raw)
    # Selected/typed a name → also try its ISO code, and vice versa.
    iso = country_code(raw)
    if iso:
        q |= Q(country__iexact=iso) | Q(country__iexact=COUNTRY_ENGLISH_NAMES[iso])
    return q
