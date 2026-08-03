from accounts.models import UserCompanyRole


from accounts.models import UserCompanyRole, Role


def has_permission(user, permission_code: str) -> bool:
    """
    Simple RBAC permission check based on:
    User -> Role -> Permissions
    """

    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    if user.is_superuser:
        return True

    if not user.role:
        return False

    return user.role.permissions.filter(code=permission_code).exists()

def role_has_permission(role, permission_code: str) -> bool:
    """
    Check permission on role including inherited base roles.
    """
    while role:
        if role.permissions.filter(code=permission_code).exists():
            return True
        role = role.base_role
    return False


def get_effective_permissions(role):
    """
    Return all permissions including inherited ones.
    """
    permissions = set()

    while role:
        permissions.update(role.permissions.all())
        role = role.base_role

    return permissions


def _micro_statuses(user):
    """Statuses of the Micro-Franchise nodes `user` owns (empty when none).

    The three predicates below all answer questions about the same small set, so
    they share this one fetch instead of each running its own EXISTS — these run
    on every request via the sidebar context processor and again inside the
    views. Returns a frozenset so callers can only ask membership questions.

    Scoped to the company the user is acting as, like every other franchise
    capability: a Micro-Franchise bought by company A does not make the same
    user a certifier while they are acting as company B."""
    if not user or not getattr(user, "is_authenticated", False):
        return frozenset()
    # Imported lazily to avoid a circular import at module load.
    from accounts.constants import FranchiseLevel
    from accounts.utils.franchise_access import owned_franchise_nodes
    return frozenset(
        owned_franchise_nodes(user)
        .filter(franchise_level=FranchiseLevel.MICRO)
        .values_list("franchise_status", flat=True)
    )


def is_micro_franchise_owner(user):
    """True when `user` owns an ACTIVE Micro-Franchise node.

    A Micro-Franchise owner "is also a consultant" (spec §9.1): they may certify
    companies and earn plan commissions just like a Standard Consultant. Keying
    on the node's ACTIVE status means suspending the Micro-Franchise revokes the
    capability automatically (spec §9.1.5 / suspension rule)."""
    from accounts.constants import FranchiseUnitStatus
    return FranchiseUnitStatus.ACTIVE in _micro_statuses(user)


def owns_micro_franchise(user):
    """True when the user owns a Micro-Franchise node in any live state (ACTIVE or
    SUSPENDED). Drives sidebar visibility of the certify/commission tabs so a
    suspended Micro owner still sees them (and gets a 'suspended' message on
    access) rather than the tabs silently vanishing."""
    from accounts.constants import FranchiseUnitStatus
    live = {FranchiseUnitStatus.ACTIVE, FranchiseUnitStatus.SUSPENDED}
    return bool(_micro_statuses(user) & live)


def is_suspended_micro_owner(user):
    """True when the user owns a SUSPENDED Micro-Franchise and has no ACTIVE one —
    i.e. they'd be a certifier if reactivated. Lets the certify/commission pages
    show a 'your account is suspended' message instead of a blunt 403."""
    from accounts.constants import FranchiseUnitStatus
    statuses = _micro_statuses(user)
    return (
        FranchiseUnitStatus.SUSPENDED in statuses
        and FranchiseUnitStatus.ACTIVE not in statuses
    )


def can_certify_companies(user):
    """Who may review/approve certification requests and earn plan commissions
    (spec §9.1.2, §11 'Certify companies' / 'Sell user plans'):

      • Superusers (platform oversight)
      • Standard Consultants (the base certifier role)
      • Micro-Franchise owners (a consultant-level franchise — §9.1)
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
    if role_code == "consultant":
        return True
    return is_micro_franchise_owner(user)
