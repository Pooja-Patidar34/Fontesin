from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import PermissionDenied

from accounts.models import User, UserRole, Role, Tenant, Company,AuditLog
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip

@login_required
def user_list(request):
    if not has_permission(request.user, "user.view"):
        raise PermissionDenied()

    tenant_id = request.GET.get("tenant") or None
    company_id = request.GET.get("company") or None
    page_number = request.GET.get("page", 1)

    if request.user.is_superuser:
        qs = User.objects.select_related("tenant")
        tenants = Tenant.objects.order_by("name")

        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
            companies = Company.objects.filter(tenant_id=tenant_id)

            if company_id:
                qs = qs.filter(usercompany__company_id=company_id).distinct()
        else:
            companies = Company.objects.none()
            company_id = None
    else:
        qs = User.objects.filter(tenant=request.user.tenant)
        tenants = None
        companies = Company.objects.filter(tenant=request.user.tenant)

        if company_id:
            qs = qs.filter(usercompany__company_id=company_id).distinct()

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 9)

    try:
        page_obj = paginator.page(page_number)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/users.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
            "tenants": tenants,
            "companies": companies,
            "selected_tenant": tenant_id,
            "selected_company": company_id,
            "active_menu": "users"

        },
    )

@login_required
def toggle_user(request, user_id):
    if not has_permission(request.user, "user.manage"):
        raise PermissionDenied()

    if request.user.is_superuser:
        user = get_object_or_404(User, id=user_id)
    else:
        user = get_object_or_404(
            User,
            id=user_id,
            tenant=request.user.tenant,
        )

    old_status = user.is_active

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    action = "user.activated" if user.is_active else "user.deactivated"

    AuditLog.objects.create(
        tenant=user.tenant,
        actor=request.user,
        action=action,
        entity_type="User",
        entity_id=user.id,
        metadata={
            "user_email": user.email,
            "old_status": old_status,
            "new_status": user.is_active,
        },
        ip_address=get_client_ip(request),
    )

    return redirect("admin:users")


@login_required
def assign_roles(request, user_id):
    if not has_permission(request.user, "role.manage"):
        raise PermissionDenied()

    if request.user.is_superuser:
        user = get_object_or_404(User, id=user_id)
        roles = Role.objects.filter(tenant=user.tenant)
    else:
        user = get_object_or_404(
            User,
            id=user_id,
            tenant=request.user.tenant,
        )
        roles = Role.objects.filter(tenant=request.user.tenant)

    if request.method == "POST":

        # Old roles (UUID → str)
        old_role_ids = list(
            UserRole.objects.filter(user=user)
            .values_list("role_id", flat=True)
        )

        old_roles_str = [str(rid) for rid in old_role_ids]

        # New roles (already strings, but normalize)
        new_role_ids = request.POST.getlist("roles")
        new_roles_str = [str(rid) for rid in new_role_ids]

        # Reset roles
        UserRole.objects.filter(user=user).delete()

        for role_id in new_role_ids:
            UserRole.objects.create(user=user, role_id=role_id)


        AuditLog.objects.create(
            tenant=user.tenant,
            actor=request.user,
            action="roles_updated",
            entity_type="User",
            entity_id=user.id,
            metadata={
                "old_roles": old_roles_str,
                "new_roles": new_roles_str,
            },
            ip_address=get_client_ip(request),
        )

        return redirect("admin:users")

    return render(
        request,
        "dashboard/assign_roles.html",
        {
            "user": user,
            "roles": roles,
            "active_menu": "users"
        },
    )


@login_required
def role_list(request):
    if not has_permission(request.user, "role.view"):
        raise PermissionDenied()
    roles = Role.objects.filter(tenant=request.user.tenant)
    return render(request, "dashboard/roles.html", {"roles": roles,"active_menu": "roles"})
