def has_permission(user, permission_code: str) -> bool:
    """
    Checks whether a user has a given permission code
    via roles assigned to the user.

    Example permission_code:
        - "company.view"
        - "company.manage"
        - "user.view"
        - "role.manage"
    """

    if not user or not user.is_authenticated:
        return False

    if not user.is_active:
        return False

    # Superuser / staff shortcut (optional but practical)
    if user.is_staff:
        return True

    return user.userrole_set.filter(
        role__permissions__code=permission_code
    ).exists()
