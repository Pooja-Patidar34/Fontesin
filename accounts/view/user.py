from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import User,UserRole,Role,AuditLog
from accounts.utils.permissions import has_permission


@login_required
def user_list(request):
    if not has_permission(request.user, "user.view"):
        return HttpResponseForbidden()

    users = User.objects.filter(
        tenant=request.user.tenant
    )

    return render(
        request,
        "dashboard/users.html",
        {"users": users},
    )


@login_required
def toggle_user(request, user_id):
    if not has_permission(request.user, "user.manage"):
        return HttpResponseForbidden()

    user = get_object_or_404(
        User,
        id=user_id,
        tenant=request.user.tenant,
    )

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    return redirect("admin:users")


@login_required
def assign_roles(request, user_id):
    if not has_permission(request.user, "role.manage"):
        return HttpResponseForbidden()

    user = get_object_or_404(
        User,
        id=user_id,
        tenant=request.user.tenant,
    )

    roles = Role.objects.filter(tenant=request.user.tenant)

    if request.method == "POST":
        UserRole.objects.filter(user=user).delete()
        for role_id in request.POST.getlist("roles"):
            UserRole.objects.create(user=user, role_id=role_id)
        return redirect("admin:users")

    return render(
        request,
        "dashboard/assign_roles.html",
        {"user": user, "roles": roles},
    )


@login_required
def audit_logs(request):
    if not has_permission(request.user, "audit.view"):
        return HttpResponseForbidden()

    logs = AuditLog.objects.filter(
        tenant=request.user.tenant
    )[:200]

    return render(
        request,
        "dashboard/audit_logs.html",
        {"logs": logs},
    )

@login_required
def role_list(request):
    if not has_permission(request.user, "role.view"):
        return HttpResponseForbidden()

    roles = Role.objects.filter(tenant=request.user.tenant)
    return render(request, "dashboard/roles.html", {"roles": roles})
