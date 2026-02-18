from accounts.models import UserRole

def admin_context(request):
    is_tenant_admin = False

    if request.user.is_authenticated and not request.user.is_superuser:
        try:
            user_role = UserRole.objects.select_related("role").get(user=request.user)
            is_tenant_admin = user_role.role.name == "tenant_admin"
        except UserRole.DoesNotExist:
            pass
    return {
        "is_tenant_admin": is_tenant_admin
    }
