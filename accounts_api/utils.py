from accounts.models import UserRole

def get_user_role(user):
    try:
        return UserRole.objects.select_related("role").get(user=user).role
    except UserRole.DoesNotExist:
        return None

def can_manage_company(user):
    if user.is_superuser:
        return True

    role = get_user_role(user)
    if not role:
        return False

    return role.permissions.filter(code="company.manage").exists()
