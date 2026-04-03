from accounts.models import UserRole, Company

def admin_context(request):
    is_tenant_admin = False
    sidebar_company_count = 0

    if request.user.is_authenticated:
        if not request.user.is_superuser:
            try:
                user_role = UserRole.objects.select_related("role").get(user=request.user)
                is_tenant_admin = user_role.role.name == "tenant_admin"
            except UserRole.DoesNotExist:
                pass

        # Company count for sidebar badge
        if request.user.is_superuser:
            sidebar_company_count = Company.objects.count()
        elif hasattr(request.user, 'tenant') and request.user.tenant:
            sidebar_company_count = Company.objects.filter(tenant=request.user.tenant).count()

    return {
        "is_tenant_admin": is_tenant_admin,
        "sidebar_company_count": sidebar_company_count,
    }
