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
