def has_permission(user, permission_code: str) -> bool:
    """
    Tenant-scoped RBAC permission check.
    """

    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    # System-level super admin
    if user.is_superuser:
        return True

    # Tenant-scoped RBAC
    return user.userrole_set.filter(
        role__tenant=user.tenant,
        role__permissions__code=permission_code,
    ).exists()
