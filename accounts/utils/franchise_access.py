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

Ownership is additionally scoped to the COMPANY the user is currently acting
as. A franchise is bought by one company, not by the person: a Business User
who owns companies A, B and C and buys a franchise while logged in as A gets a
franchise partner account for A only. Acting as B or C they are a plain
Business User with the restricted franchise rights (bug report, Aug 2026).
Every helper here therefore answers "does this user own a franchise node in
state X *for the company they are acting as*?" and is safe to call for
anonymous users.
"""

from django.db.models import Q

from accounts.constants import FranchiseLevel, FranchiseUnitStatus


# Activated states. SUSPENDED counts as activated-then-paused: the holder keeps
# historical access to the section and sees a "suspended" message inside it
# (spec §6.2) rather than the tabs silently vanishing.
LIVE_STATUSES = [FranchiseUnitStatus.ACTIVE, FranchiseUnitStatus.SUSPENDED]


def scoping_company(user):
    """The company whose franchises `user` may act on right now, or None when
    the question isn't company-scoped at all.

    Deliberately NOT ``billing.utils.resolve_active_company``: that resolver
    guesses (primary company, else the oldest) when a multi-company owner has
    made no selection, and a guess is the wrong basis for REVOKING a
    capability — it would hide a real franchise behind an arbitrary company.
    Only two answers are certain:

      • an explicit session selection stashed by ActiveCompanyMiddleware — the
        company the user picked at login, which is also what gets stamped on
        the node's ``owner_company`` when the franchise is approved;
      • the single company of a one-company owner, where there is nothing to
        pick.

    Everything else (no company at all — consultants, coordinators; or a
    multi-company owner outside a request, e.g. a management command) returns
    None and leaves the query unscoped. In the app itself that gap is closed by
    ActiveCompanyMiddleware, which forces a multi-company Business User to the
    picker before any page loads.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    selected = getattr(user, "_active_company", None)
    if selected is not None:
        return selected

    from accounts.models import Company

    owned = list(Company.objects.filter(owner_user=user)[:2])
    return owned[0] if len(owned) == 1 else None


def scope_to_active_company(qs, user):
    """Restrict a franchise-node queryset to the company `user` acts as.

    Nodes with a blank ``owner_company`` stay visible in every company context:
    they are pre-Jul-2026 rows and admin- or parent-created nodes that were
    never attributed to a company, and hiding them everywhere would strand
    their holder.
    """
    company = scoping_company(user)
    if company is None:
        return qs
    return qs.filter(Q(owner_company=company) | Q(owner_company__isnull=True))


def scope_applications_to_active_company(qs, user):
    """The `scope_to_active_company` rule, applied to franchise APPLICATIONS.

    A request is bought for one company and stamped with it (`applicant_company`),
    exactly like the node it becomes — so it belongs to that company's context. A
    request made while acting as company A must not sit in My Requests while
    acting as company B, any more than the resulting franchise does.

    Requests with no company stay visible in every context, for the same reason
    the node rule keeps company-less nodes visible: consultants and coordinators
    have no company at all, and pre-Jul-2026 requests were never attributed to
    one, so hiding them everywhere would strand their applicant.
    """
    company = scoping_company(user)
    if company is None:
        return qs
    return qs.filter(Q(applicant_company=company) | Q(applicant_company__isnull=True))


def owned_franchise_nodes(user, statuses=None):
    """Queryset of franchise nodes (Tenant rows) owned by `user` **through the
    company they are currently acting as** (see `scope_to_active_company`).

    `statuses` filters on ``franchise_status``; omit it to include in-flight
    nodes (DRAFT / PENDING / APPROVED) that are not activated yet.
    """
    from accounts.models import Tenant

    if not user or not getattr(user, "is_authenticated", False):
        return Tenant.objects.none()
    qs = scope_to_active_company(
        Tenant.objects.filter(owner_user=user, franchise_level__isnull=False), user,
    )
    if statuses:
        qs = qs.filter(franchise_status__in=statuses)
    return qs


def all_owned_franchise_nodes(user, statuses=None):
    """Every franchise node `user` owns, across ALL of their companies.

    For the few places that are genuinely about the person rather than the
    company they are acting as — "have you ever bought a franchise" checks and
    the account-wide role cleanup after a removal.
    """
    from accounts.models import Tenant

    if not user or not getattr(user, "is_authenticated", False):
        return Tenant.objects.none()
    qs = Tenant.objects.filter(owner_user=user, franchise_level__isnull=False)
    if statuses:
        qs = qs.filter(franchise_status__in=statuses)
    return qs


def company_franchise_node(company):
    """The franchise a company already holds, or None.

    One franchise per company (product rule, Aug 2026): a Business User with
    companies A, B and C buys a franchise FOR one of them, and that company's
    slot is then taken — the request form disappears for it while the other two
    keep theirs. Any state counts, including a node that is approved but not yet
    activated: the slot is spoken for from approval onwards.

    Soft-deleted nodes are excluded by ``Tenant.objects`` (ActiveManager), so a
    franchise that was removed — by the admin or through an approved removal
    request — releases the slot and the company may buy again.
    """
    if company is None:
        return None
    from accounts.models import Tenant

    return (
        Tenant.objects.filter(owner_company=company, franchise_level__isnull=False)
        .order_by("created_at")
        .first()
    )


def company_open_application(company):
    """A company's franchise request that is still awaiting a decision, or None.

    Counted against the same one-per-company slot as an owned node: two requests
    in flight for one company could both be approved, leaving it holding two.
    A REJECTED or CANCELLED request is not open, which is what lets the form come
    back for that company after a rejection.
    """
    if company is None:
        return None
    from accounts.constants import FranchiseApplicationStatus
    from accounts.models import FranchiseApplication

    return (
        FranchiseApplication.objects.filter(
            applicant_company=company,
            application_status__in=FranchiseApplicationStatus.OPEN,
        )
        .order_by("created_at")
        .first()
    )


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
