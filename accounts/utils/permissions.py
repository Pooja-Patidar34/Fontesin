from accounts.models import RolePermission


def has_permission(user, permission_code: str) -> bool:
    """
    Tenant + company scoped RBAC permission check.
    """

    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    if user.is_superuser:
        return True

    return RolePermission.objects.filter(
        role__usercompanyrole__user_company__user=user,
        role__tenant=user.tenant,
        permission__code=permission_code,
    ).exists()




def get_effective_permissions(role):
    permissions = set()

    while role:
        permissions.update(role.permissions.all())
        role = role.base_role

    return permissions
