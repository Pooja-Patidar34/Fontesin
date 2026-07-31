"""Franchise capability checks keyed on OWNERSHIP, not on the user's role.

Holding a franchise used to be expressed by flipping the holder's role to
``franchise``. That destroyed everything the account was before: a Business
User who bought a franchise lost the company switcher, plans, partnerships and
every other business-user gate, so they could no longer act as their other
companies (bug report §4, Jul 2026).

Buying a franchise is now additive. The role stays whatever it was — the
account keeps all of its previous capabilities — and franchise management is
unlocked by the franchise nodes the user actually owns. The role *label* shown
in the UI becomes "Franchise Partner" (see ``accounts.role_i18n``), which is the
only visible change the holder asked for.

Every helper here answers "does this user own a franchise node in state X?" and
is safe to call for anonymous users.
"""

from accounts.constants import FranchiseLevel, FranchiseUnitStatus


# Activated states. SUSPENDED counts as activated-then-paused: the holder keeps
# historical access to the section and sees a "suspended" message inside it
# (spec §6.2) rather than the tabs silently vanishing.
LIVE_STATUSES = [FranchiseUnitStatus.ACTIVE, FranchiseUnitStatus.SUSPENDED]


def owned_franchise_nodes(user, statuses=None):
    """Queryset of franchise nodes (Tenant rows) owned by `user`.

    `statuses` filters on ``franchise_status``; omit it to include in-flight
    nodes (DRAFT / PENDING / APPROVED) that are not activated yet.
    """
    from accounts.models import Tenant

    if not user or not getattr(user, "is_authenticated", False):
        return Tenant.objects.none()
    qs = Tenant.objects.filter(owner_user=user, franchise_level__isnull=False)
    if statuses:
        qs = qs.filter(franchise_status__in=statuses)
    return qs


def owns_any_franchise(user):
    """True when the user holds a franchise node in ANY state, including one
    that is still awaiting activation. Used by the request flow to decide
    whether the plain "Request a Franchise" form still applies."""
    return owned_franchise_nodes(user).exists()


def is_franchise_holder(user):
    """True when the user owns at least one ACTIVATED franchise node.

    This is the gate for the whole Franchise Management section: the sidebar
    entries, the tree, sub-franchise proposals, consultant rosters and reports.
    Memoised on the user instance — a single page render asks several times
    (context processor, role label, view gate) and the answer can't change
    mid-request.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    cached = getattr(user, "_is_franchise_holder", None)
    if cached is None:
        cached = owned_franchise_nodes(user, LIVE_STATUSES).exists()
        user._is_franchise_holder = cached
    return cached


def can_add_subfranchise(user):
    """True when the user holds an activated node that CAN have children —
    i.e. any non-Micro level (a Micro is the deepest level, spec §8.2)."""
    return owned_franchise_nodes(user, LIVE_STATUSES).filter(
        franchise_level__in=[
            FranchiseLevel.MASTER, FranchiseLevel.NATIONAL, FranchiseLevel.REGIONAL,
        ]
    ).exists()


def franchise_manager_required(user):
    """True when `user` may reach the franchise-management views: the Platform
    Admin, or any account that owns an activated franchise node."""
    return bool(getattr(user, "is_superuser", False)) or is_franchise_holder(user)
