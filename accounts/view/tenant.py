from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import Company, Tenant, AuditLog
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip
from accounts.forms.tenant_form import TenantForm
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils.translation import gettext as _
import logging

business_logger = logging.getLogger("business")
technical_logger = logging.getLogger("technical")

# @login_required
# def tenant_list(request):
#     if not request.user.is_superuser:
#         raise PermissionDenied()

#     if request.method == "POST":

#         tenant_id = request.POST.get("tenant_id")

#         if tenant_id:
#             tenant = get_object_or_404(Tenant, id=tenant_id)
#             form = TenantForm(request.POST, instance=tenant)
#             action = "tenant.updated"
#             message = "Tenant updated successfully."
#         else:
#             form = TenantForm(request.POST)
#             action = "tenant.created"
#             message = "Tenant created successfully."

#         if form.is_valid():
#             tenant = form.save()

#             AuditLog.objects.create(
#                 tenant=tenant,
#                 actor=request.user,
#                 action=action,
#                 entity_type="Tenant",
#                 entity_id=tenant.id,
#                 metadata={
#                     "name": tenant.name,
#                     "is_active": tenant.is_active,
#                 },
#                 ip_address=get_client_ip(request),
#             )

#             messages.success(request, message)
#             return redirect("tenants")
#     else:
#         form = TenantForm()
    
#     qs = Tenant.objects.filter(is_deleted=False).annotate(
#         company_count=Count("companies", distinct=True),
#         user_count=Count("users", distinct=True)
#     ).order_by("name")

#     paginator = Paginator(qs, 10)
#     page_number = request.GET.get("page", 1)

#     try:
#         page_obj = paginator.page(page_number)
#     except (PageNotAnInteger, EmptyPage):
#         page_obj = paginator.page(1)

#     return render(
#         request,
#         "dashboard/tenants.html",
#         {
#             "tenants": page_obj,
#             "page_obj": page_obj,
#             "form": form,
#             "active_menu": "tenants",
#         },
#     )

@login_required
def tenant_list(request):

    role_code = (
        request.user.role.code.lower()
        if request.user.role and request.user.role.code
        else ""
    )
    is_business_user = role_code == "business_user"
    is_franchise_partner = role_code == "franchise"

    if not request.user.is_superuser and not is_business_user and not is_franchise_partner:
        raise PermissionDenied()

    if request.method == "POST":

        if not request.user.is_superuser:
            raise PermissionDenied()

        tenant_id = request.POST.get("tenant_id")

        if tenant_id:
            tenant = get_object_or_404(Tenant, id=tenant_id)
            form = TenantForm(request.POST, instance=tenant)
            action = "tenant.updated"
            message = _("Tenant updated successfully.")
        else:
            form = TenantForm(request.POST)
            action = "tenant.created"
            message = _("Tenant created successfully.")

        if form.is_valid():
            try:
                with transaction.atomic():
                    tenant = form.save()

                    AuditLog.objects.create(
                        tenant=tenant,
                        actor=request.user,
                        action=action,
                        entity_type="Tenant",
                        entity_id=tenant.id,
                        metadata={
                            "name": tenant.name,
                            "is_active": tenant.is_active,
                        },
                        ip_address=get_client_ip(request),
                    )
            except IntegrityError:
                duplicate_msg = _("A franchise with this name (or a similar one) already exists. Please choose a different name.")
                form.add_error("name", duplicate_msg)
                messages.error(request, duplicate_msg)
            else:
                messages.success(request, message)
                return redirect("tenants")
        else:
            # Surface validation errors (e.g. duplicate franchise name) as a
            # toast — the Add Franchise modal is closed once the page re-renders,
            # so the inline field error alone wouldn't be visible.
            for field, errs in form.errors.items():
                for err in errs:
                    messages.error(request, err)

    else:
        form = TenantForm()

    # SEARCH
    q = request.GET.get("q", "").strip()

    # Business user: only see their own tenant
    if is_business_user:
        qs = Tenant.objects.filter(id=request.user.tenant_id, is_deleted=False)
    elif is_franchise_partner and not request.user.is_superuser:
        # Franchise partner: only their own franchise node(s) plus descendants —
        # never a parallel branch (spec §7.1/§7.3, §9.6 "View parallel branches" =
        # No). A Brazil master must not see the US master's nodes. This mirrors
        # the Franchise Tree page's scoping via visible_node_ids().
        from accounts.view.franchise import visible_nodes_qs
        qs = visible_nodes_qs(request.user).filter(is_deleted=False)

        # Deactivated tenants are an admin-only concern: the Platform Admin needs
        # them listed to reactivate them, but a franchise partner has no action to
        # take on one, so they only ever see live tenants. `is_active` is the field
        # the Status badge renders, so this hides exactly the "Inactive" rows.
        qs = qs.filter(is_active=True)
    else:
        # Platform Admin: the full tenant list — franchise nodes AND plain
        # (non-franchise) tenants alike, active and inactive.
        qs = Tenant.objects.filter(is_deleted=False)

    if q:
        qs = qs.filter(name__icontains=q)

    if is_business_user:
        # Scope the counts to what the business user can actually see when
        # clicking through. Without this, the badge says "5 users" but the
        # users page only shows the 2 sharing a company with the requester
        # (per scope_to_own_company in user_list). Companies count likewise
        # reflects the linkage scope, not every company in the tenant.
        own_company_ids = set(
            request.user.usercompany_set.values_list("company_id", flat=True)
        )
        if request.user.primary_company_id:
            own_company_ids.add(request.user.primary_company_id)
        own_company_ids.update(
            Company.objects.filter(
                Q(consultant=request.user) | Q(owner_user=request.user)
            ).values_list("id", flat=True)
        )

        qs = qs.annotate(
            company_count=Count(
                "companies",
                filter=Q(companies__id__in=own_company_ids),
                distinct=True,
            ),
            user_count=Count(
                "users",
                filter=(
                    Q(users__primary_company_id__in=own_company_ids)
                    | Q(users__usercompany__company_id__in=own_company_ids)
                ),
                distinct=True,
            ),
        ).order_by("name")
    else:
        qs = qs.annotate(
            company_count=Count("companies", distinct=True),
            user_count=Count("users", distinct=True),
        ).order_by("name")

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        messages.error(request, _("Invalid page number. Showing the first page."))
        querydict = request.GET.copy()
        querydict["page"] = 1
        return redirect(f"{request.path}?{querydict.urlencode()}")
    except EmptyPage:
        messages.error(
            request,
            _("Page %(page)s doesn't exist. There are only %(total)s page(s). Showing the first page.")
            % {"page": page_number, "total": paginator.num_pages},
        )
        querydict = request.GET.copy()
        querydict["page"] = 1
        return redirect(f"{request.path}?{querydict.urlencode()}")

    context = {
        "tenants": page_obj,
        "page_obj": page_obj,
        "form": form,
        "active_menu": "tenants",
        "search_query": q,
        "is_business_user": is_business_user,
    }

    # For AJAX search, return only the panel partial so the client can swap it in.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "dashboard/_tenants_panel.html", context)

    return render(request, "dashboard/tenants.html", context)

@login_required
def toggle_tenant(request, tenant_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    old_status = tenant.is_active
    tenant.is_active = not tenant.is_active
    tenant.save(update_fields=["is_active"])

    action = (
        "tenant.activated"
        if tenant.is_active
        else "tenant.deactivated"
    )

    AuditLog.objects.create(
        tenant=tenant,
        actor=request.user,
        action=action,
        entity_type="Tenant",
        entity_id=tenant.id,
        metadata={
            "old_status": old_status,
            "new_status": tenant.is_active,
        },
        ip_address=get_client_ip(request),
    )

    return redirect(request.META.get("HTTP_REFERER", "tenants"))


@login_required
def tenant_detail_ajax(request, tenant_id):
    role_code = (
        request.user.role.code.lower()
        if request.user.role and request.user.role.code
        else ""
    )
    is_business_user = role_code == "business_user"
    is_franchise_partner = role_code == "franchise"

    if not request.user.is_superuser and not is_business_user and not is_franchise_partner:
        raise PermissionDenied()

    if is_business_user and str(tenant_id) != str(request.user.tenant_id):
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    return JsonResponse({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.strftime("%Y-%m-%d %H:%M"),
    })


@login_required
def tenant_delete(request, tenant_id):

    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    if request.method == "POST":

        tenant_name = tenant.name

        AuditLog.objects.create(
            tenant=tenant,   # FIXED
            actor=request.user,
            action="tenant.deleted",
            entity_type="Tenant",
            entity_id=str(tenant.id),
            metadata={
                "name": tenant_name,
            },
            ip_address=get_client_ip(request),
        )

        # Soft delete
        tenant.is_deleted = True
        tenant.save(update_fields=["is_deleted"])

        messages.success(request, _("Tenant deleted successfully."))
        return redirect("tenants")

    return render(
        request,
        "dashboard/tenant_confirm_delete.html",
        {
            "tenant": tenant,
            "active_menu": "tenants",
        },
    )