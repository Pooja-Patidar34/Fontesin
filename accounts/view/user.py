import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from accounts.models import (
    User,
    UserRole,
    Role,
    Tenant,
    Company,
    AuditLog,
    Permission,
)
from accounts.utils.permissions import has_permission, get_effective_permissions
from accounts.utils.ip import get_client_ip
from accounts.forms.certificate_form import RoleForm, PermissionForm

logger = logging.getLogger(__name__)


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

    paginator = Paginator(qs, 10)

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

    next_url = request.GET.get("next")
    return redirect(next_url or "admin:user-list")

@login_required
def user_detail_ajax(request, user_id):
    if not request.user.is_superuser and not has_permission(request.user, "user.view"):
        raise PermissionDenied()

    can_manage = (
        request.user.is_superuser
        or has_permission(request.user, "user.manage")
    )

    user = get_object_or_404(
        User.objects.select_related(
            "tenant",
            "primary_company",
            "userrole__role",
        ),
        id=user_id,
    )

    tenant = user.tenant

    roles = list(
        Role.objects.filter(tenant=tenant)
        .values("id", "name")
        .order_by("name")
    )

    companies = list(
        Company.objects.filter(tenant=tenant)
        .values("id", "name")
        .order_by("name")
    )

    return JsonResponse({
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,

        # tenant (read-only)
        "tenant": tenant.name,
        "tenant_id": str(tenant.id),

        # current selections
        "role_id": user.userrole.role.id if hasattr(user, "userrole") else None,
        "company_id": user.primary_company.id if user.primary_company else None,

        # dropdown data
        "roles": roles,
        "companies": companies,

        # capabilities
        "can_manage": can_manage,
    })


@login_required
def user_edit(request, user_id):
    if not (
        request.user.is_superuser
        or has_permission(request.user, "user.manage")
    ):
        raise PermissionDenied()

    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    user = get_object_or_404(User, id=user_id)
    tenant = user.tenant

    # update user fields
    user.full_name = request.POST.get("full_name", user.full_name)
    user.email = request.POST.get("email", user.email)
    user.is_active = request.POST.get("is_active") == "true"

    # company (tenant scoped)
    company_id = request.POST.get("company_id")
    if company_id:
        user.primary_company = get_object_or_404(
            Company, id=company_id, tenant=tenant
        )

    user.save()

    # role (tenant scoped)
    role_id = request.POST.get("role_id")
    if role_id:
        role = get_object_or_404(Role, id=role_id, tenant=tenant)
        UserRole.objects.update_or_create(
            user=user,
            defaults={"role": role}
        )

    return JsonResponse({
        "success": True,
        "message": "User updated successfully"
    })


@login_required
def assign_roles(request, user_id):
    if not has_permission(request.user, "role.manage"):
        raise PermissionDenied()

    next_url = request.GET.get("next") or request.POST.get("next")

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

        old_role_ids = list(
            UserRole.objects.filter(user=user)
            .values_list("role_id", flat=True)
        )

        old_roles_str = [str(rid) for rid in old_role_ids]

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

        return redirect(next_url or "admin:users")

    return render(
        request,
        "dashboard/assign_roles.html",
        {
            "user": user,
            "roles": roles,
            "active_menu": "users",
            "next": next_url, 
        },
    )



@login_required
def role_list(request):
    logger.info("ROLE LIST VIEW CALLED")

    if not has_permission(request.user, "role.view"):
        raise PermissionDenied()

    selected_tenant_id = request.GET.get("tenant")
    page_number = request.GET.get("page", 1)

    if request.user.is_superuser:
        roles_qs = (
            Role.objects
            .select_related("tenant", "base_role")
            .exclude(name="super_admin")
            .prefetch_related("permissions")
        )

        if selected_tenant_id:
            roles_qs = roles_qs.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.order_by("name")

    else:
        roles_qs = (
            Role.objects
            .filter(tenant=request.user.tenant)
            .select_related("base_role")
            .prefetch_related("permissions")
        )

        tenants = None
        selected_tenant_id = None

    paginator = Paginator(roles_qs, 8)  

    try:
        roles = paginator.page(page_number)
    except PageNotAnInteger:
        roles = paginator.page(1)
    except EmptyPage:
        roles = paginator.page(paginator.num_pages)

    for role in roles:
        role.effective_permission_count = len(
            get_effective_permissions(role)
        )

    permissions = Permission.objects.order_by("code")

    can_view = has_permission(request.user, "role.view")
    can_manage = has_permission(request.user, "role.manage")

    return render(
        request,
        "dashboard/roles.html",
        {
            "roles": roles,                 
            "page_obj": roles,             
            "paginator": paginator,

            "permissions": permissions,
            "tenants": tenants,
            "selected_tenant_id": selected_tenant_id,

            "active_menu": "access-control",
            "active_submenu": "roles",
            "can_manage": can_manage,
            "can_view": can_view,
        },
    )



@login_required
@transaction.atomic
def save_role(request):
    if request.method != "POST":
        raise PermissionDenied()

    if not has_permission(request.user, "role.manage"):
        raise PermissionDenied()

    role_id = request.POST.get("role_id")
    name = request.POST.get("name")
    permission_ids = request.POST.getlist("permissions")

    if request.user.is_superuser:
        tenant_id = request.POST.get("tenant")
        if not tenant_id:
            messages.error(request, "Tenant is required.")
            return redirect("admin:roles")
        tenant = get_object_or_404(Tenant, id=tenant_id)
    else:
        tenant = request.user.tenant

    if role_id:
        role = get_object_or_404(Role, id=role_id, tenant=tenant)
    else:
        role = Role.objects.create(
            tenant=tenant,
            name=name,
        )

    role.name = name
    role.save()
    role.permissions.set(permission_ids)
    next_url = request.POST.get("next") or reverse("admin:roles")
    return redirect(next_url)



@login_required
def role_detail_ajax(request, role_id):

    if not has_permission(request.user, "role.view"):
        raise PermissionDenied()

    if request.user.is_superuser:
        role = get_object_or_404(Role, id=role_id)
    else:
        role = get_object_or_404(
            Role,
            id=role_id,
            tenant=request.user.tenant
        )

    permissions = list(
        role.permissions.values_list("id", flat=True)
    )

    return JsonResponse({
        "id": str(role.id),
        "name": role.name,
        "tenant": {
            "id": str(role.tenant.id),
            "name": role.tenant.name,
        },
        "permissions": [str(p) for p in permissions],
    })


@login_required
def permission_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    if request.method == "POST":
        permission_id = request.POST.get("permission_id")

        if permission_id:
            permission = get_object_or_404(Permission, id=permission_id)
            form = PermissionForm(request.POST, instance=permission)
        else:
            form = PermissionForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Permission saved successfully.")
            return redirect("admin:permissions")

    else:
        form = PermissionForm()

    permissions = Permission.objects.order_by("code")

    return render(
        request,
        "dashboard/permissions.html",
        {
            "permissions": permissions,
            "form": form,
            "active_menu": "access-control",
            "active_submenu": "permissions",
        },
    )



