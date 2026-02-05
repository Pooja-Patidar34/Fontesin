from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import User,UserRole,Role,AuditLog
from accounts.utils.permissions import has_permission
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied



@login_required
def user_list(request):
    if not has_permission(request.user, "user.view"):
        raise PermissionDenied()

    qs = User.objects.filter(
        tenant=request.user.tenant
    ).order_by("-created_at")

    paginator = Paginator(qs, 7)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "dashboard/users.html",
        {
            "users": page_obj,
            "page_obj": page_obj,
        },
    )


@login_required
def toggle_user(request, user_id):
    if not has_permission(request.user, "user.manage"):
        raise PermissionDenied()

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
        raise PermissionDenied()

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
def role_list(request):
    if not has_permission(request.user, "role.view"):
        raise PermissionDenied
    roles = Role.objects.filter(tenant=request.user.tenant)
    return render(request, "dashboard/roles.html", {"roles": roles})
