from accounts.models import UserCompanyRole


def has_permission(user, permission_code: str) -> bool:
    """
    Tenant + company scoped RBAC permission check.
    Uses Role.permissions (ManyToMany) ONLY.
    """

    # Basic guards
    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    # Superuser = allow all
    if user.is_superuser:
        return True

    # Fetch roles assigned to the user via company mapping
    roles = (
        UserCompanyRole.objects
        .filter(
            user_company__user=user,
            role__tenant=user.tenant,
        )
        .select_related("role", "role__base_role")
        .prefetch_related("role__permissions", "role__base_role__permissions")
        .values_list("role", flat=True)
    )

    if not roles:
        return False

    # Check permissions via role inheritance
    for role in roles:
        if role_has_permission(role, permission_code):
            return True

    return False


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
