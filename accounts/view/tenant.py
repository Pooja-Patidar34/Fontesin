from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, get_object_or_404, redirect

from accounts.models import Company, Tenant, AuditLog
from accounts.constants import FranchiseUnitStatus
from django.utils import timezone
from accounts.utils.permissions import has_permission
from accounts.utils.ip import get_client_ip
from accounts.forms.tenant_form import TenantForm
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils.translation import gettext as _, ngettext
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

# Newest franchise first. The list was alphabetical by name, which buried a
# just-created franchise on whatever page its initial happened to fall on —
# "Zenith" landed on page 4 and looked like the creation had failed. `name` is
# the tiebreaker so rows sharing a timestamp keep a stable order across pages
# (an unordered tail makes the paginator repeat or skip rows).
_LIST_ORDER = ("-created_at", "name")


@login_required
def tenant_list(request):

    role_code = (
        request.user.role.code.lower()
        if request.user.role and request.user.role.code
        else ""
    )
    # A franchise holder is identified by the nodes they own, not by a role —
    # a Business User who buys a franchise keeps the business_user role, so
    # test franchise ownership FIRST and let it win over the business-user
    # branch below (which would otherwise scope them to their own tenant and
    # hide the franchise they just bought).
    from accounts.utils.franchise_access import is_franchise_holder
    is_franchise_partner = is_franchise_holder(request.user)
    is_business_user = role_code == "business_user" and not is_franchise_partner

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
        ).order_by(*_LIST_ORDER)
    else:
        qs = qs.annotate(
            company_count=Count("companies", distinct=True),
            user_count=Count("users", distinct=True),
        ).order_by(*_LIST_ORDER)

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
    update_fields = ["is_active"]

    # A franchise node carries a separate lifecycle status (`franchise_status`)
    # that the Franchise Tree and every franchise rule read. This generic
    # activate/deactivate toggle used to move only `is_active`, so a franchise
    # deactivated here still showed ACTIVE in the tree and kept its franchise
    # rights. Mirror the toggle onto `franchise_status` using the same
    # ACTIVE<->SUSPENDED transition as the dedicated Suspend/Reactivate action
    # (accounts/view/franchise.py:franchise_suspend), so both surfaces agree and
    # the deactivation actually takes effect. Only that one transition is
    # mirrored; pending/terminated/expired nodes keep their lifecycle status.
    synced_franchise_status = False
    if tenant.franchise_level is not None:
        if not tenant.is_active and tenant.franchise_status == FranchiseUnitStatus.ACTIVE:
            tenant.franchise_status = FranchiseUnitStatus.SUSPENDED
            tenant.suspended_at = timezone.now()
            update_fields += ["franchise_status", "suspended_at", "updated_at"]
            synced_franchise_status = True
        elif tenant.is_active and tenant.franchise_status == FranchiseUnitStatus.SUSPENDED:
            tenant.franchise_status = FranchiseUnitStatus.ACTIVE
            try:
                tenant.clean()  # re-check exclusivity/parent on the way back to ACTIVE
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect(request.META.get("HTTP_REFERER", "tenants"))
            update_fields += ["franchise_status", "updated_at"]
            synced_franchise_status = True

    try:
        tenant.save(update_fields=update_fields)
    except IntegrityError:
        # Reactivation lost the Micro-Franchise exclusivity race (another Micro is
        # already active in this territory). Leave the node as-is and explain.
        messages.error(
            request,
            _("Cannot reactivate: a Micro-Franchise already occupies this territory."),
        )
        return redirect(request.META.get("HTTP_REFERER", "tenants"))

    # Keep a Micro owner's consultant self-assignment in step with the node's
    # status (certify rights track it), mirroring franchise_suspend.
    if synced_franchise_status:
        try:
            from accounts.view.franchise import _sync_micro_owner_assignment
            from accounts.constants import ConsultantAssignmentStatus
            _sync_micro_owner_assignment(
                tenant,
                ConsultantAssignmentStatus.ACTIVE if tenant.is_active
                else ConsultantAssignmentStatus.SUSPENDED,
            )
        except Exception:
            technical_logger.exception(
                "toggle_tenant: micro-owner assignment sync failed for %s", tenant.id
            )

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
    # See tenant_list: franchise access follows node ownership, so a Business
    # User holding a franchise reads their franchise subtree here rather than
    # being pinned to their own tenant.
    from accounts.utils.franchise_access import is_franchise_holder
    is_franchise_partner = is_franchise_holder(request.user)
    is_business_user = role_code == "business_user" and not is_franchise_partner

    if not request.user.is_superuser and not is_business_user and not is_franchise_partner:
        raise PermissionDenied()

    if is_business_user and str(tenant_id) != str(request.user.tenant_id):
        raise PermissionDenied()

    if is_franchise_partner and not request.user.is_superuser:
        from accounts.view.franchise import visible_node_ids
        allowed = visible_node_ids(request.user)
        if str(tenant_id) != str(request.user.tenant_id) and tenant_id not in allowed:
            raise PermissionDenied()

    tenant = get_object_or_404(
        Tenant.objects.select_related(
            "owner_user", "owner_company", "parent", "approved_by", "created_by"
        ),
        id=tenant_id,
    )

    return JsonResponse({
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.strftime("%Y-%m-%d %H:%M"),
        # Read-only rows for the View modal. The keys above stay exactly as they
        # were — Edit still binds id/name/is_active to the form — while "View"
        # used to show only those three and told the user next to nothing about
        # the franchise or who holds it.
        "details": _tenant_detail_rows(tenant),
    })


def _fmt_dt(value):
    """Local-time 'YYYY-MM-DD HH:MM', or empty when the timestamp is unset."""
    if not value:
        return ""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _tenant_detail_rows(tenant):
    """
    Label/value rows shown in the read-only Franchise Details modal.

    Labels are translated here rather than in JS so they follow the request
    language like the rest of the page. Blank values are dropped by the caller's
    template code, so a plain (non-franchise) partition simply shows fewer rows
    instead of a column of dashes.
    """
    owner = tenant.owner_user
    territory = " / ".join(
        part for part in (
            tenant.territory_country,
            tenant.territory_region,
            tenant.territory_city,
            tenant.territory_local_area,
        ) if part
    )

    rows = [
        (_("Owner"), owner.display_name if owner else ""),
        (_("Owner email"), owner.email if owner else ""),
        (_("Owner company"), tenant.owner_company.name if tenant.owner_company else ""),
        (_("Franchise level"), tenant.get_franchise_level_display() or ""),
        (_("Parent franchise"), tenant.parent.name if tenant.parent else ""),
        (_("Franchise status"), tenant.get_franchise_status_display() or ""),
        (_("Fee status"), tenant.get_franchise_fee_status_display() or ""),
        (_("Contract status"), tenant.get_contract_status_display() or ""),
        (_("Territory"), territory),
        # Exclusivity only means something on a franchise node, so it stays out
        # of the list for a plain partition.
        (_("Exclusive territory"),
         "" if not tenant.franchise_level else (_("Yes") if tenant.is_exclusive else _("No"))),
        (_("Sub-franchises"), str(tenant.children.count()) if tenant.franchise_level else ""),
        (_("Users"), str(tenant.users.count())),
        (_("Companies"), str(tenant.companies.count())),
        (_("Domain"), tenant.domain or ""),
        (_("Slug"), tenant.slug),
        (_("Approved by"), tenant.approved_by.display_name if tenant.approved_by else ""),
        (_("Approved on"), _fmt_dt(tenant.approved_at)),
        (_("Activated on"), _fmt_dt(tenant.activated_at)),
        (_("Suspended on"), _fmt_dt(tenant.suspended_at)),
        (_("Terminated on"), _fmt_dt(tenant.terminated_at)),
        (_("Created by"), tenant.created_by.display_name if tenant.created_by else ""),
        (_("Created on"), _fmt_dt(tenant.created_at)),
        (_("Last updated"), _fmt_dt(tenant.updated_at)),
    ]

    return [{"label": label, "value": value} for label, value in rows if value]


@login_required
def tenant_delete(request, tenant_id):

    if not request.user.is_superuser:
        raise PermissionDenied()

    tenant = get_object_or_404(Tenant, id=tenant_id)

    if request.method == "POST":

        tenant_name = tenant.name

        # A franchise node is not just a hidden row: its sub-franchises, the
        # consultants under it, the applications behind it and its holders' roles
        # all have to be wound down together, or the subtree survives as live
        # ACTIVE nodes hanging off a parent the rest of the app filters out.
        # remove_franchise does the whole cascade (and its own audit rows).
        if tenant.franchise_level is not None:
            from accounts.utils.franchise_removal import remove_franchise

            result = remove_franchise(
                tenant, actor=request.user, ip_address=get_client_ip(request),
            )
            descendants = result["descendant_count"]
            if descendants:
                messages.success(
                    request,
                    ngettext(
                        "%(name)s was removed, along with the %(count)s sub-franchise beneath it.",
                        "%(name)s was removed, along with the %(count)s sub-franchises beneath it.",
                        descendants,
                    ) % {"name": tenant_name, "count": descendants},
                )
            else:
                messages.success(
                    request, _("%(name)s was removed.") % {"name": tenant_name},
                )
            return redirect("tenants")

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