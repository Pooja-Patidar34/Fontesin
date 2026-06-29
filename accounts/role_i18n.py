"""Display labels for user roles (gettext context ``roles``)."""

from django.utils.translation import pgettext


def localized_role_label(user) -> str:
    """Return a locale-aware label for *user*'s role."""
    if not user or not getattr(user, "is_authenticated", False):
        return pgettext("roles", "User")
    if user.is_superuser:
        return pgettext("roles", "Platform Admin")

    role = getattr(user, "role", None)
    if not role:
        return pgettext("roles", "User")

    code = (role.code or "").lower()
    name_key = (role.name or "").lower().replace(" ", "_")
    key = code or name_key

    labels = {
        "tenant_admin": pgettext("roles", "Tenant Admin"),
        "business_user": pgettext("roles", "Business User"),
        "consultant": pgettext("roles", "Consultant"),
        "coordinator": pgettext("roles", "Coordinator"),
        "franchise": pgettext("roles", "Franchise Partner"),
        "admin": pgettext("roles", "Admin"),
    }
    if key in labels:
        return labels[key]

    return (role.name or role.code or "").replace("_", " ").title()
