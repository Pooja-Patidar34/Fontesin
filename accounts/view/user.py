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
def add_user(request):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid request"})

    try:
        data = request.POST

        # --------------------
        # Required fields
        # --------------------
        email = data.get("email")
        password = data.get("password")
        first_name = data.get("first_name")
        last_name = data.get("last_name")

        if not all([email, password, first_name, last_name]):
            return JsonResponse({
                "status": False,
                "message": "Required fields missing"
            })

        # --------------------
        # Tenant resolution
        # --------------------
        if request.user.is_superuser:
            tenant_id = data.get("tenant")
            if not tenant_id:
                return JsonResponse({
                    "status": False,
                    "message": "Tenant is required"
                })
            tenant = Tenant.objects.get(id=tenant_id)
        else:
            tenant = request.user.tenant

        # --------------------
        # Company (tenant scoped)
        # --------------------
        company = None
        company_id = data.get("primary_company")
        if company_id:
            company = Company.objects.get(id=company_id, tenant=tenant)

        # --------------------
        # Create User
        # --------------------
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            tenant=tenant,
            primary_company=company,
            is_active=data.get("is_active") == "true",

            # Contact
            phone=data.get("phone"),
            national_prefix=data.get("national_prefix"),

            # Personal
            birth_date=data.get("birth_date") or None,
            ethnicity=data.get("ethnicity"),
            gender=data.get("gender"),

            # Profile
            preferred_language=data.get("preferred_language"),
            bio=data.get("bio"),
            notes=data.get("notes"),
            photo_url=data.get("photo_url"),

            # Address
            address_line1=data.get("address_line1"),
            address_line2=data.get("address_line2"),
            city=data.get("city"),
            state_region=data.get("state_region"),
            postal_code=data.get("postal_code"),
            country=data.get("country"),
        )

        # --------------------
        # Role assignment
        # --------------------
        role_id = data.get("role")
        if role_id:
            role = Role.objects.get(id=role_id, tenant=tenant)
            UserRole.objects.create(user=user, role=role)

        return JsonResponse({"status": True, "user_id": str(user.id)})

    except Exception as e:
        return JsonResponse({
            "status": False,
            "message": str(e)
        })

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
    return redirect(next_url or "user-list")

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
            "role",          # 🔹 direct FK
        ),
        id=user_id,
    )

    tenant = user.tenant

    # 🔹 GLOBAL roles (only 3)
    roles = list(
        Role.objects
        .values("id", "name")
        .order_by("name")
    )

    # 🔹 Companies remain tenant-scoped
    companies = list(
        Company.objects
        .filter(tenant=tenant)
        .values("id", "name")
        .order_by("name")
    )

    return JsonResponse({

        # --------------------
        # Core Identity
        # --------------------
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,

        # --------------------
        # Tenant (read-only)
        # --------------------
        "tenant": tenant.name,
        "tenant_id": str(tenant.id),

        # --------------------
        # Company & Role
        # --------------------
        "company_id": str(user.primary_company_id) if user.primary_company_id else None,
        "company_name": user.primary_company.name if user.primary_company else None,

        "role_id": str(user.role_id) if user.role else None,
        "role_name": user.role.name if user.role else None,

        # --------------------
        # Contact
        # --------------------
        "phone": user.phone,
        "national_prefix": user.national_prefix,

        # --------------------
        # Personal
        # --------------------
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "ethnicity": user.ethnicity,
        "gender": user.gender,

        # --------------------
        # Profile
        # --------------------
        "preferred_language": user.preferred_language,
        "bio": user.bio,
        "notes": user.notes,
        "photo_url": user.photo_url,

        # --------------------
        # Address
        # --------------------
        "address_line1": user.address_line1,
        "address_line2": user.address_line2,
        "city": user.city,
        "state_region": user.state_region,
        "postal_code": user.postal_code,
        "country": user.country,

        # --------------------
        # Meta
        # --------------------
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),

        # --------------------
        # Dropdown Data
        # --------------------
        "roles": roles,
        "companies": companies,

        # --------------------
        # Capabilities
        # --------------------
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

    try:
        # -------------------------------
        # Tenant scoping
        # -------------------------------
        if request.user.is_superuser:
            user = get_object_or_404(User, id=user_id)
        else:
            user = get_object_or_404(
                User,
                id=user_id,
                tenant=request.user.tenant,
            )

        tenant = user.tenant

        with transaction.atomic():

            # -------------------------------
            # Capture old values (audit)
            # -------------------------------
            old_data = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "is_active": user.is_active,
                "phone": user.phone,
                "primary_company_id": (
                    str(user.primary_company_id)
                    if user.primary_company_id else None
                ),
                "role_id": str(user.role_id) if user.role_id else None,
            }

            # -------------------------------
            # Core Identity
            # -------------------------------
            user.first_name = request.POST.get("first_name", user.first_name)
            user.last_name = request.POST.get("last_name", user.last_name)
            user.email = request.POST.get("email", user.email)
            user.is_active = request.POST.get("is_active") == "true"

            # -------------------------------
            # Contact
            # -------------------------------
            user.phone = request.POST.get("phone", user.phone)
            user.national_prefix = request.POST.get(
                "national_prefix", user.national_prefix
            )

            # -------------------------------
            # Personal
            # -------------------------------
            user.birth_date = (
                request.POST.get("birth_date") or user.birth_date
            )
            user.ethnicity = request.POST.get("ethnicity", user.ethnicity)
            user.gender = request.POST.get("gender", user.gender)

            # -------------------------------
            # Profile
            # -------------------------------
            user.preferred_language = request.POST.get(
                "preferred_language", user.preferred_language
            )
            user.bio = request.POST.get("bio", user.bio)
            user.notes = request.POST.get("notes", user.notes)
            user.photo_url = request.POST.get("photo_url", user.photo_url)

            # -------------------------------
            # Address
            # -------------------------------
            user.address_line1 = request.POST.get(
                "address_line1", user.address_line1
            )
            user.address_line2 = request.POST.get(
                "address_line2", user.address_line2
            )
            user.city = request.POST.get("city", user.city)
            user.state_region = request.POST.get(
                "state_region", user.state_region
            )
            user.postal_code = request.POST.get(
                "postal_code", user.postal_code
            )
            user.country = request.POST.get("country", user.country)

            # -------------------------------
            # Company (tenant-scoped)
            # -------------------------------
            company_id = request.POST.get("company_id")
            if company_id:
                user.primary_company = get_object_or_404(
                    Company,
                    id=company_id,
                    tenant=tenant,
                )

            # -------------------------------
            # Role (GLOBAL)
            # -------------------------------
            role_id = request.POST.get("role_id")
            if role_id:
                role = get_object_or_404(Role, id=role_id)
                user.role = role

            user.full_clean()
            user.save()

        # -------------------------------
        # Audit Log (non-blocking)
        # -------------------------------
        try:
            AuditLog.objects.create(
                tenant=tenant,
                actor=request.user,
                action="user.updated",
                entity_type="User",
                entity_id=user.id,
                metadata={
                    "old": old_data,
                    "new": {
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "email": user.email,
                        "is_active": user.is_active,
                        "phone": user.phone,
                        "primary_company_id": (
                            str(user.primary_company_id)
                            if user.primary_company_id else None
                        ),
                        "role_id": str(user.role_id) if user.role_id else None,
                    },
                },
                ip_address=get_client_ip(request),
            )
        except Exception:
            pass  # audit must never block the action

        return JsonResponse(
            {
                "success": True,
                "message": "User updated successfully",
            }
        )

    except IntegrityError:
        return JsonResponse(
            {"success": False, "message": "Email already exists"},
            status=400,
        )

    except ValidationError as e:
        return JsonResponse(
            {"success": False, "message": e.message_dict},
            status=400,
        )

    except PermissionDenied:
        raise

    except Exception:
        return JsonResponse(
            {
                "success": False,
                "message": "Unable to update user at the moment",
            },
            status=500,
        )

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
        return redirect(next_url or "users")

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


# @login_required
# def role_list(request):
#     logger.info("ROLE LIST VIEW CALLED")

#     if not has_permission(request.user, "role.view"):
#         raise PermissionDenied()

#     selected_tenant_id = request.GET.get("tenant")
#     page_number = request.GET.get("page", 1)

#     if request.user.is_superuser:
#         roles_qs = (
#             Role.objects
#             .select_related("tenant", "base_role")
#             .exclude(name="super_admin")
#             .prefetch_related("permissions")
#         )

#         if selected_tenant_id:
#             roles_qs = roles_qs.filter(tenant_id=selected_tenant_id)

#         tenants = Tenant.objects.order_by("name")

#     else:
#         roles_qs = (
#             Role.objects
#             .filter(tenant=request.user.tenant)
#             .select_related("base_role")
#             .prefetch_related("permissions")
#         )

#         tenants = None
#         selected_tenant_id = None

#     paginator = Paginator(roles_qs, 8)  

#     try:
#         roles = paginator.page(page_number)
#     except PageNotAnInteger:
#         roles = paginator.page(1)
#     except EmptyPage:
#         roles = paginator.page(paginator.num_pages)

#     for role in roles:
#         role.effective_permission_count = len(
#             get_effective_permissions(role)
#         )

#     permissions = Permission.objects.order_by("code")

#     can_view = has_permission(request.user, "role.view")
#     can_manage = has_permission(request.user, "role.manage")

#     return render(
#         request,
#         "dashboard/roles.html",
#         {
#             "roles": roles,                 
#             "page_obj": roles,             
#             "paginator": paginator,

#             "permissions": permissions,
#             "tenants": tenants,
#             "selected_tenant_id": selected_tenant_id,

#             "active_menu": "access-control",
#             "active_submenu": "roles",
#             "can_manage": can_manage,
#             "can_view": can_view,
#         },
#     )



@login_required
def role_list(request):
    logger.info("ROLE LIST VIEW CALLED")

    if not has_permission(request.user, "role.view"):
        raise PermissionDenied()

    page_number = request.GET.get("page", 1)

    # Roles are GLOBAL now
    roles_qs = (
        Role.objects
        .exclude(name="super_admin")  # optional
        .prefetch_related("permissions")
    )

    if request.user.role and request.user.role.name == "tenant_admin":
        roles_qs = roles_qs.exclude(name="tenant_admin")

    paginator = Paginator(roles_qs, 8)

    try:
        roles = paginator.page(page_number)
    except PageNotAnInteger:
        roles = paginator.page(1)
    except EmptyPage:
        roles = paginator.page(paginator.num_pages)

    for role in roles:
        role.effective_permission_count = role.permissions.count()

    permissions = Permission.objects.order_by("code")

    return render(
        request,
        "dashboard/roles.html",
        {
            "roles": roles,
            "page_obj": roles,
            "paginator": paginator,

            "permissions": permissions,

            "active_menu": "access-control",
            "active_submenu": "roles",

            "can_manage": has_permission(request.user, "role.manage"),
            "can_view": True,
        },
    )



@login_required
@transaction.atomic
def save_role(request):
    if request.method != "POST":
        raise PermissionDenied()

    if not (request.user.is_superuser or has_permission(request.user, "role.manage")):
        raise PermissionDenied()

    role_id = request.POST.get("role_id")
    permission_ids = request.POST.getlist("permissions")

    print("Received permission IDs:", permission_ids)

    if not role_id:
        messages.error(request, "Role is required.")
        return redirect("roles")

    role = get_object_or_404(Role, id=role_id)

    print("Before count:", role.permissions.count())

    old_permissions = list(
        role.permissions.values_list("id", flat=True)
    )

    role.permissions.set(permission_ids)

    # Convert UUIDs → strings for JSONField
    AuditLog.objects.create(
        tenant=request.user.tenant,
        actor=request.user,
        action="role.permissions_updated",
        entity_type="Role",
        entity_id=str(role.id),
        metadata={
            "old_permissions": [str(pid) for pid in old_permissions],
            "new_permissions": [str(pid) for pid in permission_ids],
        },
        ip_address=get_client_ip(request),
    )

    messages.success(request, "Role permissions updated successfully.")
    return redirect(request.POST.get("next") or "roles")


@login_required
def role_detail_ajax(request, role_id):

    if not has_permission(request.user, "role.view"):
        raise PermissionDenied()

    # Roles are GLOBAL now
    role = get_object_or_404(Role, id=role_id)

    permissions = list(
        role.permissions.values_list("id", flat=True)
    )

    return JsonResponse({
        "id": str(role.id),
        "name": role.name,
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
            return redirect("permissions")

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



