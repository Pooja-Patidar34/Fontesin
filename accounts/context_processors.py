import json

from accounts.models import UserRole, Company, CompanyConnection


def admin_context(request):
    is_tenant_admin = False
    sidebar_company_count = 0
    plan_features_json = "{}"
    is_free_plan = False
    is_basic_plan = False
    is_pro_plan = False
    is_global_plan = False
    is_basic_business_user = False
    is_pro_business_user = False
    is_global_business_user = False
    is_paid_business_user = False
    pending_partnership_count = 0
    show_partnership_upgrade_banner = False

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

        # Plan-feature flags for sidebar gating (superusers get everything).
        from billing.utils import get_user_plan
        if request.user.is_superuser:
            plan_features_json = json.dumps({"__superuser__": True})
        else:
            plan = get_user_plan(request.user)
            comparison = (plan.comparison if plan and plan.comparison else {}) or {}
            features = {k: bool(v) for k, v in comparison.items()}
            plan_features_json = json.dumps(features)
            is_free_plan = bool(plan and plan.code == "free")
            is_basic_plan = bool(plan and plan.code == "basic")
            is_pro_plan = bool(plan and plan.code == "pro")
            is_global_plan = bool(plan and plan.code == "global")

            role_code = ""
            if request.user.role and request.user.role.code:
                role_code = request.user.role.code.lower()
            is_business_user = role_code == "business_user"
            is_basic_business_user = is_basic_plan and is_business_user
            is_pro_business_user = is_pro_plan and is_business_user
            is_global_business_user = is_global_plan and is_business_user
            is_paid_business_user = (
                is_basic_business_user or is_pro_business_user or is_global_business_user
            )

            # Pending incoming partnership requests on companies this user
            # owns. We surface the count site-wide so a banner can prompt
            # Free-plan users to upgrade — partnership_action requires a
            # paid plan, so without an upgrade these requests are stuck.
            owned_company_ids = Company.objects.filter(
                owner_user=request.user
            ).values_list("id", flat=True)
            if owned_company_ids:
                pending_partnership_count = CompanyConnection.objects.filter(
                    company_id__in=list(owned_company_ids),
                    status=CompanyConnection.STATUS_PENDING,
                ).count()
                # Show the upgrade banner only for users who can't act on the
                # request right now: free plan, no plan at all, and no other
                # path to approve. Paid plans see the requests on the
                # Partnerships page directly.
                if pending_partnership_count and is_business_user and not is_paid_business_user:
                    show_partnership_upgrade_banner = True

    return {
        "is_tenant_admin": is_tenant_admin,
        "sidebar_company_count": sidebar_company_count,
        "plan_features_json": plan_features_json,
        "is_free_plan": is_free_plan,
        "is_basic_plan": is_basic_plan,
        "is_pro_plan": is_pro_plan,
        "is_global_plan": is_global_plan,
        "is_basic_business_user": is_basic_business_user,
        "is_pro_business_user": is_pro_business_user,
        "is_global_business_user": is_global_business_user,
        "is_paid_business_user": is_paid_business_user,
        # Back-compat alias for existing template gates that haven't been swapped over.
        "is_basic_or_pro_business_user": is_paid_business_user,
        "pending_partnership_count": pending_partnership_count,
        "show_partnership_upgrade_banner": show_partnership_upgrade_banner,
    }
