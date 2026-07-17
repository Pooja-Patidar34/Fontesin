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


def is_micro_franchise_owner(user):
    """True when `user` owns an ACTIVE Micro-Franchise node.

    A Micro-Franchise owner "is also a consultant" (spec §9.1): they may certify
    companies and earn plan commissions just like a Standard Consultant. Keying
    on the node's ACTIVE status means suspending the Micro-Franchise revokes the
    capability automatically (spec §9.1.5 / suspension rule)."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    # Imported lazily to avoid a circular import at module load.
    from accounts.models import Tenant
    from accounts.constants import FranchiseLevel, FranchiseUnitStatus
    return Tenant.objects.filter(
        owner_user=user,
        franchise_level=FranchiseLevel.MICRO,
        franchise_status=FranchiseUnitStatus.ACTIVE,
    ).exists()


def owns_micro_franchise(user):
    """True when the user owns a Micro-Franchise node in any live state (ACTIVE or
    SUSPENDED). Drives sidebar visibility of the certify/commission tabs so a
    suspended Micro owner still sees them (and gets a 'suspended' message on
    access) rather than the tabs silently vanishing."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from accounts.models import Tenant
    from accounts.constants import FranchiseLevel, FranchiseUnitStatus
    return Tenant.objects.filter(
        owner_user=user,
        franchise_level=FranchiseLevel.MICRO,
        franchise_status__in=[FranchiseUnitStatus.ACTIVE, FranchiseUnitStatus.SUSPENDED],
    ).exists()


def is_suspended_micro_owner(user):
    """True when the user owns a SUSPENDED Micro-Franchise and has no ACTIVE one —
    i.e. they'd be a certifier if reactivated. Lets the certify/commission pages
    show a 'your account is suspended' message instead of a blunt 403."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from accounts.models import Tenant
    from accounts.constants import FranchiseLevel, FranchiseUnitStatus
    qs = Tenant.objects.filter(owner_user=user, franchise_level=FranchiseLevel.MICRO)
    return (
        qs.filter(franchise_status=FranchiseUnitStatus.SUSPENDED).exists()
        and not qs.filter(franchise_status=FranchiseUnitStatus.ACTIVE).exists()
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
