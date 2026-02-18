from accounts.models import UserCompanyRole


from accounts.models import UserCompanyRole, Role


def has_permission(user, permission_code: str) -> bool:
    """
    Tenant + company scoped RBAC permission check.
    Uses Role.permissions (ManyToMany) ONLY.
    """

    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    if user.is_superuser:
        return True

    roles = (
        Role.objects
        .filter(
            usercompanyrole__user_company__user=user,
            tenant=user.tenant,
        )
        .select_related("base_role")
        .prefetch_related("permissions", "base_role__permissions")
        .distinct()
    )

    if not roles.exists():
        return False

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
