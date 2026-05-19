from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

from accounts.models import Company, Tenant, AuditLog, CompanyConnection
from accounts.constants import (
    CountryChoices,
    COUNTRY_STATES,
    COUNTRY_FLAGS,
    LEGAL_FORMS_BY_COUNTRY,
    CompanyClassificationChoices,
)
from django.db.models import Q
from accounts.utils.permissions import has_permission
from accounts.view.saved_filter import (
    FILTER_FIELDS,
    _is_basic_business_user,
    _is_basic_or_pro_business_user,
    _plan_code_for_business_user,
)
from billing.utils import PLAN_REGIONS, _region_for_country


# Extra free-text spellings seen in Company.country (mapped by ISO code).
# The user's profile stores the ISO code; companies store free-text names.
_COUNTRY_ALIASES = {
    "US": ("USA", "United States of America", "U.S.", "U.S.A."),
    "GB": ("UK", "U.K.", "Great Britain"),
    "AE": ("UAE", "U.A.E."),
    "KR": ("Korea", "South Korea"),
    "CZ": ("Czechia",),
}


def _country_match_q(country_code):
    """Build a Q that matches Company.country against the user's country code,
    including the CountryChoices label and common free-text aliases."""
    variants = [country_code]
    label = dict(CountryChoices.CHOICES).get(country_code)
    if label:
        variants.append(label)
    variants.extend(_COUNTRY_ALIASES.get(country_code, ()))
    q = Q()
    for v in variants:
        q |= Q(country__iexact=v)
    return q
from accounts.utils.ip import get_client_ip
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.template.loader import render_to_string

from accounts.forms.company_form import CompanyForm
from accounts.utils.certification_routing import find_consultant_for_company


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _ordered_country_choices():
    """Pinned countries (USA, UK) first, the rest alphabetical by name.
    Used to drive the filter-bar country picker so the active markets are
    one click away without forcing-hide other countries."""
    pinned_codes = list(CountryChoices.PINNED)
    label_by_code = dict(CountryChoices.CHOICES)
    pinned = [(c, label_by_code[c]) for c in pinned_codes if c in label_by_code]
    others = sorted(
        [(c, n) for c, n in CountryChoices.CHOICES if c not in pinned_codes],
        key=lambda kv: kv[1].lower(),
    )
    return {"pinned": pinned, "others": others}


@login_required
def company_filter_autocomplete(request):
    """Type-ahead source for the Company Database filter bar.

    field=name → matches Company.name
    field=city → matches Company.city
    field=state → matches Company.state (also scopes to selected country if
                  the request includes ?country= so e.g. US state list is
                  filtered server-side too)

    Capped at 15 hits, always distinct.
    """
    field = (request.GET.get("field") or "").strip().lower()
    q = (request.GET.get("q") or "").strip()
    country = (request.GET.get("country") or "").strip().upper()

    if field not in {"name", "city", "state"}:
        return JsonResponse({"results": []})

    qs = Company.objects.filter(is_active=True)
    if country:
        qs = qs.filter(country__iexact=country)
    if q:
        qs = qs.filter(**{f"{field}__icontains": q})

    values = (
        qs.exclude(**{f"{field}__isnull": True})
          .exclude(**{f"{field}__exact": ""})
          .values_list(field, flat=True)
          .distinct()
          .order_by(field)[:15]
    )
    return JsonResponse({"results": list(values)})


@login_required
@transaction.atomic
def company_list(request):

    # -------------------------------
    # VIEW PERMISSION
    # -------------------------------
    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    next_url = request.POST.get("next") or request.GET.get("next")

    # -------------------------------
    # CREATE / UPDATE
    # -------------------------------
    if request.method == "POST":

        if not has_permission(request.user, "company.manage"):
            raise PermissionDenied()

        company_id = request.POST.get("company_id")

        if company_id in ("", None, "undefined"):
            company_id = None

        # ---------- UPDATE ----------
        if company_id:
            role_name = (request.user.role.name or "").lower() if request.user.role else ""

            if request.user.is_superuser:
                company = get_object_or_404(Company, id=company_id)
            elif role_name == "tenant_admin":
                company = get_object_or_404(
                    Company,
                    id=company_id,
                    tenant=request.user.tenant,
                )
            else:
                # Match list-view scoping (linkage-based, cross-tenant).
                company = get_object_or_404(
                    Company.objects.filter(
                        Q(tenant=request.user.tenant)
                        | Q(consultant=request.user)
                        | Q(owner_user=request.user)
                        | Q(primary_users=request.user)
                        | Q(usercompany__user=request.user)
                    ).distinct(),
                    id=company_id,
                )

            old_data = {
                "name": company.name,
                "registration_id": company.registration_id,
                "classification": company.classification,
                "is_active": company.is_active,
            }

            form = CompanyForm(
                request.POST,
                request.FILES,
                instance=company,
                user=request.user,
            )
            action = "company.updated"

        # ---------- CREATE ----------
        else:
            company = None
            old_data = None

            form = CompanyForm(
                request.POST,
                request.FILES,
                user=request.user,
            )
            action = "company.created"

        if form.is_valid():
            company = form.save(commit=False)

            # Enforce tenant safety
            if not request.user.is_superuser:
                company.tenant = request.user.tenant

            # Auto-link the creator as owner on new rows so the narrow-scope
            # listing (see GET branch below) shows the company they just added.
            if not company_id and not request.user.is_superuser and not company.owner_user_id:
                company.owner_user = request.user

            # Auto-link the consultant FK when a consultant creates a company.
            # This is what makes downstream commission attribution work — when
            # a business user later picks this company as their primary, the
            # 10% commission flows back to this consultant on every approved
            # paid subscription.
            creator_role_code = ""
            if request.user.role and request.user.role.code:
                creator_role_code = request.user.role.code.lower()
            if not company_id and creator_role_code == "consultant" and not company.consultant_id:
                company.consultant = request.user

            # New companies created through the BU onboarding form are not yet
            # vetted — flag them as awaiting consultant certification, hold
            # them out of the public directory until approved, and route them
            # to a consultant in the same locality. Consultants who create
            # companies for their own clients bypass this gate (they're the
            # ones doing the certifying), so the toggle only fires for
            # non-consultant authors.
            if not company_id and creator_role_code != "consultant":
                company.certification_status = "pending"
                company.is_active = False
                if not company.consultant_id:
                    routed = find_consultant_for_company(company)
                    if routed and routed.id != request.user.id:
                        company.consultant = routed

            company.save()
            form.save_m2m()

            # ---------- AUDIT LOG ----------
            try:
                AuditLog.objects.create(
                    tenant=company.tenant,
                    actor=request.user,
                    action=action,
                    entity_type="Company",
                    entity_id=company.id,
                    metadata={
                        "old": old_data,
                        "new": {
                            "name": company.name,
                            "registration_id": company.registration_id,
                            "classification": company.classification,
                            "is_active": company.is_active,
                        },
                    },
                    ip_address=get_client_ip(request),
                )
            except Exception:
                # Never block core flow for audit failures
                pass

            success_msg = (
                "Company updated successfully."
                if company_id
                else "Certification request submitted. An admin will review your company shortly."
            )

            if _is_ajax(request):
                row_html = render_to_string(
                    "dashboard/_company_row.html",
                    {
                        "company": company,
                        "can_view": has_permission(request.user, "company.view"),
                        "can_manage": has_permission(request.user, "company.manage"),
                    },
                    request=request,
                )
                return JsonResponse({
                    "ok": True,
                    "created": not company_id,
                    "message": success_msg,
                    "row_html": row_html,
                    "company_id": str(company.id),
                })

            messages.success(request, success_msg)
            return redirect(next_url or "companies")

        else:
            # Surface validation errors (e.g. duplicate name+tenant) so the user sees why the save failed.
            if _is_ajax(request):
                # Plain {field: [str, ...]} dict — `form.errors` is a Django
                # ErrorDict/ErrorList structure that doesn't always survive
                # the JsonResponse serializer cleanly across versions, and
                # the frontend wants real strings to render inline next to
                # each input. First-error-only is enough for the modal UI.
                errors_plain = {}
                flat_errors = []
                for field, errs in form.errors.items():
                    str_errs = [str(e) for e in errs]
                    errors_plain[field] = str_errs
                    if field == "__all__":
                        flat_errors.extend(str_errs)
                    else:
                        label = (
                            form.fields[field].label
                            if field in form.fields and form.fields[field].label
                            else field.replace("_", " ").title()
                        )
                        flat_errors.extend(f"{label}: {e}" for e in str_errs)
                # Always include a specific message — never let the frontend
                # fall back to "Could not save company. Please check the form."
                # which tells the user nothing about WHICH field failed.
                message = (
                    " ".join(flat_errors)
                    or "Please correct the highlighted fields and try again."
                )
                return JsonResponse(
                    {"ok": False, "errors": errors_plain, "message": message},
                    status=400,
                )

            for field, errs in form.errors.items():
                for err in errs:
                    if field == "__all__":
                        messages.error(request, err)
                    else:
                        label = form.fields[field].label or field.replace("_", " ").title()
                        messages.error(request, f"{label}: {err}")

    # -------------------------------
    # GET (LIST + EMPTY FORM)
    # -------------------------------
    else:
        form = CompanyForm(user=request.user)

    # -------------------------------
    # FILTERING / PAGINATION
    # -------------------------------
    selected_tenant_id = request.GET.get("tenant")
    page_number = request.GET.get("page", 1)

    if request.user.is_superuser:
        queryset = Company.objects.select_related("tenant")

        if selected_tenant_id:
            queryset = queryset.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.filter(is_active=True).order_by("name")

    else:
        role_name = (request.user.role.name or "").lower() if request.user.role else ""
        if role_name == "tenant_admin":
            # Tenant admins see every company in their tenant.
            queryset = Company.objects.filter(tenant=request.user.tenant)
        else:
            # Everyone else (business_user, consultant, coordinator, franchise)
            # sees only companies they're directly linked to. No tenant
            # pre-filter because registration lets users pick a company from
            # any tenant, so a linked company may live outside their own tenant.
            # `usercompany__user` covers approved partnership connections —
            # `partnership_action` adds a UserCompany row on approve so the
            # requester gains list + detail access.
            linkage_q = (
                Q(consultant=request.user)
                | Q(owner_user=request.user)
                | Q(primary_users=request.user)
                | Q(usercompany__user=request.user)
            )

            # Business-user discovery scope, by plan:
            #   global → all active companies worldwide
            #   pro    → all active companies in the user's country
            #   basic  → all active companies in the user's state (within country)
            #   free   → same scope as basic; the "no details" restriction is
            #            applied by the templates via is_free_plan.
            # User.country is an ISO code ("US"); Company.country is free-text,
            # so match across code + label + common aliases. User.state_region
            # holds the user's state; matched case-insensitive against
            # Company.state.
            #
            # Fallbacks: if the user is missing the data needed for their
            # tier's scope (no country for pro, no state for basic/free), we
            # widen by one level rather than show an empty list — keeps
            # existing accounts working until they fill profile in.
            plan_code = _plan_code_for_business_user(request.user)
            user_country = (request.user.country or "").strip().upper()
            user_state = (request.user.state_region or "").strip()

            scope_q = None
            if plan_code == "global":
                scope_q = Q(is_active=True)
            elif plan_code == "pro" and user_country:
                scope_q = _country_match_q(user_country) & Q(is_active=True)
            elif plan_code in ("basic", "free") and user_country:
                base = _country_match_q(user_country) & Q(is_active=True)
                if user_state:
                    scope_q = base & Q(state__iexact=user_state)
                else:
                    # Missing state on profile → fall back to country-wide so
                    # the user isn't locked out. They can narrow via filter bar.
                    scope_q = base

            if scope_q is not None:
                linkage_q = linkage_q | scope_q

            queryset = Company.objects.filter(linkage_q).distinct()

        # Honor the ?tenant=<id> query param for non-superusers too. The
        # Tenants page links each company-count badge to /companies/?tenant=<id>
        # so the user can drill into a specific tenant's companies. Without
        # this intersect, the param was silently dropped and the page showed
        # the user's full unscoped list — confusing the count and the result.
        # The filter intersects with the existing scope (tenant_admin's own
        # tenant, or business users' linkage + discovery), so users only ever
        # see companies they're already permitted to see.
        if selected_tenant_id:
            queryset = queryset.filter(tenant_id=selected_tenant_id)

        tenants = Tenant.objects.filter(
            id=request.user.tenant_id
        )

    # -------------------------------
    # LOCATION FILTERS (paid business users + consultants)
    # -------------------------------
    is_paid_bu = _is_basic_or_pro_business_user(request.user)
    role_code = (request.user.role.code or "").lower() if request.user.role else ""
    can_filter_companies = is_paid_bu or role_code == "consultant"
    applied_filters = {}
    if can_filter_companies:
        # Match modes vary per field:
        #   exact      — country (ISO code), entity_type, classification (enum)
        #   contains   — state, city, name (so "Tex" matches "Texas")
        #   enrichment — naics lives on the related CompanyEnrichment row
        #   keywords   — OR across name/website/registration_id
        EXACT_FIELDS = {"country", "entity_type", "classification"}
        CONTAINS_FIELDS = {"state", "city", "name"}

        for key in FILTER_FIELDS:
            value = (request.GET.get(key) or "").strip()
            if not value:
                continue
            applied_filters[key] = value

            if key in EXACT_FIELDS:
                queryset = queryset.filter(**{f"{key}__iexact": value})
            elif key in CONTAINS_FIELDS:
                queryset = queryset.filter(**{f"{key}__icontains": value})
            elif key == "naics":
                # Misnamed historical filter — now covers NACE *and* NAICS.
                # Match against:
                #   - the typed NACE FK (Company.nace_code) by code prefix
                #     OR title substring
                #   - the typed NAICS FK (Company.naics_code) the same way
                #   - the legacy free-text Company.industry_code column
                #     (so older rows still surface)
                #   - the enrichment row's denormalized NAICS code/desc
                #     from bulk CSV imports
                queryset = queryset.filter(
                    Q(nace_code__code__istartswith=value)
                    | Q(nace_code__title__icontains=value)
                    | Q(naics_code__code__istartswith=value)
                    | Q(naics_code__title__icontains=value)
                    | Q(industry_code__icontains=value)
                    | Q(enrichment__naics_code__icontains=value)
                    | Q(enrichment__naics_description__icontains=value)
                )
            elif key == "keywords":
                # Free-form search — split on whitespace, each token must hit
                # at least one of the searched columns (AND across tokens,
                # OR across columns within a token).
                for token in value.split():
                    queryset = queryset.filter(
                        Q(name__icontains=token)
                        | Q(website__icontains=token)
                        | Q(registration_id__icontains=token)
                    )

        queryset = queryset.distinct()

    # Order: the user's own companies first (owner_user / primary_company /
    # consultant), then everyone else. Within each group, newest first so
    # freshly-added/imported companies surface at the top instead of being
    # hidden alphabetically across many pages.
    #
    # NOTE: we use Exists() for the primary_users membership instead of
    # Q(primary_users=request.user). The latter forces a LEFT JOIN through
    # UserCompany and multiplies rows for any company that has more than
    # one UserCompany row, which surfaced as visible duplicates in the
    # companies list.
    from django.db.models import Case, When, IntegerField, Value, Exists, OuterRef
    from accounts.models import UserCompany

    is_primary_user_for_company = UserCompany.objects.filter(
        company=OuterRef("pk"),
        user=request.user,
    )
    own_q = (
        Q(owner_user=request.user)
        | Q(consultant=request.user)
        | Q(_user_is_primary=True)
    )
    # Pull tenant + nace_code in the same query as the rows so the
    # _company_row.html template can render company.tenant.name and
    # company.nace_code.code / .title without an extra DB hit per row.
    queryset = queryset.select_related("tenant", "nace_code").annotate(
        _user_is_primary=Exists(is_primary_user_for_company),
    ).annotate(
        _own_rank=Case(
            When(own_q, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    )
    paginator = Paginator(queryset.order_by("_own_rank", "-created_at"), 10)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        messages.error(request, "Invalid page number. Showing the first page.")
        querydict = request.GET.copy()
        querydict["page"] = 1
        return redirect(f"{request.path}?{querydict.urlencode()}")
    except EmptyPage:
        messages.error(
            request,
            f"Page {page_number} doesn't exist. There are only {paginator.num_pages} page(s). Showing the first page.",
        )
        querydict = request.GET.copy()
        querydict["page"] = 1
        return redirect(f"{request.path}?{querydict.urlencode()}")

    pending_ids = set()
    accepted_ids = set()
    if is_paid_bu:
        page_company_ids = [c.id for c in page_obj.object_list]
        for company_id, status in (
            CompanyConnection.objects
            .filter(user=request.user, company_id__in=page_company_ids)
            .values_list("company_id", "status")
        ):
            if status == CompanyConnection.STATUS_ACCEPTED:
                accepted_ids.add(company_id)
            elif status == CompanyConnection.STATUS_PENDING:
                pending_ids.add(company_id)

    # Companies a paid business user (basic / pro / global) is allowed to
    # "View": companies they're directly linked to (owner, consultant,
    # primary_users, UserCompany) plus any company they've established an
    # approved partnership with, plus their primary company. Discovery-only
    # rows (region / worldwide listings) stay gated until the partnership is
    # accepted by the company owner.
    viewable_ids = set(accepted_ids)
    if not request.user.is_superuser and request.user.primary_company_id:
        viewable_ids.add(request.user.primary_company_id)
    if is_paid_bu and page_obj.object_list:
        page_company_ids = [c.id for c in page_obj.object_list]
        linked_ids = Company.objects.filter(id__in=page_company_ids).filter(
            Q(consultant=request.user)
            | Q(owner_user=request.user)
            | Q(primary_users=request.user)
            | Q(usercompany__user=request.user)
        ).values_list("id", flat=True)
        viewable_ids.update(linked_ids)

    # -------------------------------
    # RENDER
    # -------------------------------
    context = {
        "companies": page_obj,
        "page_obj": page_obj,
        "tenants": tenants,
        "selected_tenant_id": selected_tenant_id,
        "form": form,
        "can_manage": has_permission(request.user, "company.manage"),
        "can_view": has_permission(request.user, "company.view"),
        "active_menu": "companies",
        "next": request.get_full_path(),
        "applied_filters": applied_filters,
        "pending_ids": pending_ids,
        "accepted_ids": accepted_ids,
        "viewable_ids": viewable_ids,
        # Country → state map consumed by the modal's dependent dropdown JS,
        # rendered server-side via {% json_script %}.
        "country_states": COUNTRY_STATES,
        # Filter-bar data — countries pinned (US, GB) above the rest with
        # flags; legal-form options swapped per selected country;
        # classification list for the Field-of-activity dropdown.
        "filter_country_choices": _ordered_country_choices(),
        "filter_country_flags": COUNTRY_FLAGS,
        "filter_legal_forms_by_country": LEGAL_FORMS_BY_COUNTRY,
        "filter_classifications": CompanyClassificationChoices.CHOICES,
    }

    # AJAX GET (pagination): return only the rendered fragments. The same
    # request path serves both full-page and partial responses; the client
    # opts in by sending X-Requested-With.
    if request.method == "GET" and _is_ajax(request):
        return JsonResponse({
            "rows_html": render_to_string(
                "dashboard/_companies_rows.html", context, request=request
            ),
            "pagination_html": render_to_string(
                "dashboard/_companies_pagination.html", context, request=request
            ),
        })

    return render(request, "dashboard/companies.html", context)





# @login_required
# @transaction.atomic
# def company_list(request):

#     if not has_permission(request.user, "company.view"):
#         raise PermissionDenied()

#     next_url = request.POST.get("next") or request.GET.get("next")

#     if request.method == "POST":

#         if not has_permission(request.user, "company.manage"):
#             raise PermissionDenied()

#         company_id = request.POST.get("company_id")

#         if company_id:
#             if request.user.is_superuser:
#                 company = get_object_or_404(Company, id=company_id)
#             else:
#                 company = get_object_or_404(
#                     Company,
#                     id=company_id,
#                     tenant=request.user.tenant
#                 )

#             old_data = {
#                 "name": company.name,
#                 "registration_id": company.registration_id,
#                 "is_active": company.is_active,
#                 "classification": company.classification,
#             }

#             form = CompanyForm(request.POST, instance=company, user=request.user)
#             action = "company.updated"

#         else:
#             form = CompanyForm(request.POST, user=request.user)
#             old_data = None
#             action = "company.created"

#         if form.is_valid():
#             company = form.save(commit=False)

#             # Enforce tenant restriction
#             if not request.user.is_superuser:
#                 company.tenant = request.user.tenant

#             company.save()

#             try:
#                 AuditLog.objects.create(
#                     tenant=company.tenant,
#                     actor=request.user,
#                     action=action,
#                     entity_type="Company",
#                     entity_id=company.id,
#                     metadata={
#                         "old": old_data,
#                         "new": {
#                             "name": company.name,
#                             "registration_id": company.registration_id,
#                             "is_active": company.is_active,
#                             "classification": company.classification,
#                         },
#                     },
#                     ip_address=get_client_ip(request),
#                 )
#             except Exception:
#                 pass

#             messages.success(request, "Company saved successfully.")

#             return redirect(next_url or "companies")

#     else:
#         form = CompanyForm(user=request.user)


#     selected_tenant_id = request.GET.get("tenant")
#     page_number = request.GET.get("page", 1)

#     if request.user.is_superuser:
#         queryset = Company.objects.select_related("tenant")

#         if selected_tenant_id:
#             queryset = queryset.filter(tenant_id=selected_tenant_id)

#         tenants = Tenant.objects.order_by("name")

#     else:
#         queryset = Company.objects.filter(tenant=request.user.tenant)
#         tenants = Tenant.objects.filter(id=request.user.tenant_id)


#     paginator = Paginator(queryset.order_by("name"), 10)
#     page_obj = paginator.get_page(page_number)

#     return render(
#         request,
#         "dashboard/companies.html",
#         {
#             "companies": page_obj,
#             "page_obj": page_obj,
#             "tenants": tenants,
#             "selected_tenant_id": selected_tenant_id,
#             "form": form,
#             "can_manage": has_permission(request.user, "company.manage"),
#             "can_view": has_permission(request.user, "company.view"),
#             "active_menu": "companies",
#             "next": request.get_full_path(),
#         },
#     )


@login_required
@transaction.atomic
def company_delete(request, company_id):

    # -------------------------------
    # PERMISSION CHECK
    # -------------------------------
    if not has_permission(request.user, "company.manage"):
        raise PermissionDenied()

    # Consultants get CRU on companies but not delete — block here.
    role_code = ""
    if request.user.role and request.user.role.code:
        role_code = request.user.role.code.lower()
    if role_code == "consultant":
        raise PermissionDenied()

    if request.method != "POST":
        raise PermissionDenied()

    # -------------------------------
    # FETCH COMPANY (TENANT SAFE)
    # -------------------------------
    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    else:
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )

    company_name = company.name
    tenant = company.tenant

    # -------------------------------
    # DELETE
    # -------------------------------
    company.delete()

    # -------------------------------
    # AUDIT LOG
    # -------------------------------
    try:
        AuditLog.objects.create(
            tenant=tenant,
            actor=request.user,
            action="company.deleted",
            entity_type="Company",
            entity_id=company_id,
            metadata={
                "company_name": company_name,
            },
            ip_address=get_client_ip(request),
        )
    except Exception:
        pass

    messages.success(request, "Company deleted successfully.")

    referer = request.META.get("HTTP_REFERER")

    if referer:
        return redirect(referer)

    return redirect(reverse("companies"))


@login_required
def toggle_company(request, company_id):
    if not has_permission(request.user, "company.manage"):
        raise PermissionDenied()

    role_name = (request.user.role.name or "").lower() if request.user.role else ""

    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    elif role_name == "tenant_admin":
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )
    else:
        # Match the edit-path scoping (linkage-based, cross-tenant). Global /
        # Pro business users can toggle a partner company once the owner has
        # approved the connection — that approval adds the UserCompany row
        # picked up by `usercompany__user`.
        company = get_object_or_404(
            Company.objects.filter(
                Q(tenant=request.user.tenant)
                | Q(consultant=request.user)
                | Q(owner_user=request.user)
                | Q(primary_users=request.user)
                | Q(usercompany__user=request.user)
            ).distinct(),
            id=company_id,
        )

    old_status = company.is_active
    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])

    action = "company.activated" if company.is_active else "company.deactivated"

    AuditLog.objects.create(
        tenant=company.tenant,
        actor=request.user,
        action=action,
        entity_type="Company",
        entity_id=company.id,
        metadata={
            "company_name": company.name,
            "old_status": old_status,
            "new_status": company.is_active,
        },
        ip_address=get_client_ip(request),
    )

    referer = request.META.get("HTTP_REFERER")

    if referer:
        return redirect(referer)

    return redirect(reverse("companies"))



@login_required
def company_detail_ajax(request, company_id):

    if not has_permission(request.user, "company.view"):
        raise PermissionDenied()

    role_name = (request.user.role.name or "").lower() if request.user.role else ""

    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    elif role_name == "tenant_admin":
        # Tenant admins manage every company in their tenant.
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )
    else:
        # Business users, consultants, coordinators, franchises see only
        # companies they're linked to — matches the list-view scoping,
        # which is cross-tenant because registration lets you pick a
        # company from any tenant. `usercompany__user` covers approved
        # partnership connections so the requester can View the company
        # data once the owner approves; discovery-only rows from the
        # paid-plan list view stay 404 here until the partnership is
        # accepted.
        scope_q = (
            Q(tenant=request.user.tenant)
            | Q(consultant=request.user)
            | Q(owner_user=request.user)
            | Q(primary_users=request.user)
            | Q(usercompany__user=request.user)
        )

        company = get_object_or_404(
            Company.objects.filter(scope_q).distinct(),
            id=company_id,
        )

    enrichment = getattr(company, "enrichment", None)

    return JsonResponse({
        # --------------------
        # Company (Core)
        # --------------------
        "company": {
            "id": str(company.id),
            "tenant": str(company.tenant.id),
            "name": company.name,
            "registration_id": company.registration_id,
            "classification": company.classification,
            "entity_type": company.entity_type,

            "address_line1": company.address_line1,
            "address_line2": company.address_line2,
            "house_number": company.house_number,
            "district": company.district,
            "region": company.region,
            "city": company.city,
            "state": company.state,
            "postal_code": company.postal_code,
            "country": company.country,

            "latitude": str(company.latitude) if company.latitude else None,
            "longitude": str(company.longitude) if company.longitude else None,

            "year_established": company.year_established,
            "industry_code": company.industry_code,
            # NACE/NAICS picker payload. The hidden form input takes the
            # UUID (`nace_code`); the picker's visible "code — title" text
            # is populated from `nace_code_display`. Both null when unset.
            "nace_code": str(company.nace_code_id) if company.nace_code_id else None,
            "nace_code_display": (
                f"{company.nace_code.code} — {company.nace_code.title}"
                if company.nace_code_id else None
            ),
            "naics_code": str(company.naics_code_id) if company.naics_code_id else None,
            "naics_code_display": (
                f"{company.naics_code.code} — {company.naics_code.title}"
                if company.naics_code_id else None
            ),
            "keywords": company.keywords,
            "employee_count_range": company.employee_count_range,

            "phone": company.phone,
            "phone_secondary": company.phone_secondary,
            "fax": company.fax,
            "website": company.website,
            "contact_email": company.contact_email,

            # Absolute URL so the template can render the logo in the modal
            # header regardless of how the page was opened (e.g. via API or
            # an internal redirect).
            "logo_url": request.build_absolute_uri(company.logo.url) if company.logo else None,
            "certification_status": company.certification_status,
            "certified_by_name": (
                (f"{company.certified_by.first_name} {company.certified_by.last_name}".strip()
                 or company.certified_by.email)
                if company.certified_by else None
            ),
            "certified_at": company.certified_at.isoformat() if company.certified_at else None,

            "is_active": company.is_active,
        },

        # --------------------
        # Company Enrichment
        # --------------------
        "enrichment": {
            "naics_code": enrichment.naics_code if enrichment else None,
            "naics_description": enrichment.naics_description if enrichment else None,

            "sic2_code": enrichment.sic2_code if enrichment else None,
            "sic4_code": enrichment.sic4_code if enrichment else None,
            "sic6_code": enrichment.sic6_code if enrichment else None,

            "sic2_description": enrichment.sic2_description if enrichment else None,
            "sic4_description": enrichment.sic4_description if enrichment else None,
            "sic6_description": enrichment.sic6_description if enrichment else None,
            "sic_division": enrichment.sic_division if enrichment else None,

            "exact_sales_volume": (
                str(enrichment.exact_sales_volume)
                if enrichment and enrichment.exact_sales_volume else None
            ),
            "sales_range": enrichment.sales_range if enrichment else None,
            "sales_code": enrichment.sales_code if enrichment else None,

            "exact_employee_count": enrichment.exact_employee_count if enrichment else None,
            "employee_range": enrichment.employee_range if enrichment else None,
            "employee_code": enrichment.employee_code if enrichment else None,

            "business_type": enrichment.business_type if enrichment else None,
            "location_type": enrichment.location_type if enrichment else None,

            "year_started": enrichment.year_started if enrichment else None,
            "month_started": enrichment.month_started if enrichment else None,

            "franchise": enrichment.franchise if enrichment else None,
            "chain": enrichment.chain if enrichment else None,
            "home_office": enrichment.home_office if enrichment else None,

            "median_income_census_area": (
                str(enrichment.median_income_census_area)
                if enrichment and enrichment.median_income_census_area else None
            ),
            "mean_housing_census_area": (
                str(enrichment.mean_housing_census_area)
                if enrichment and enrichment.mean_housing_census_area else None
            ),

            "ebiz_score": enrichment.ebiz_score if enrichment else None,
            "ebiz_decile": enrichment.ebiz_decile if enrichment else None,
            "ebiz_percentile": enrichment.ebiz_percentile if enrichment else None,

            "monthly_telco_spend": (
                str(enrichment.monthly_telco_spend)
                if enrichment and enrichment.monthly_telco_spend else None
            ),
            "monthly_data_spend": (
                str(enrichment.monthly_data_spend)
                if enrichment and enrichment.monthly_data_spend else None
            ),
            "number_of_lines": enrichment.number_of_lines if enrichment else None,
            "number_of_pcs": enrichment.number_of_pcs if enrichment else None,

            "is_manufacturing": enrichment.is_manufacturing if enrichment else None,
            "is_subsidiary": enrichment.is_subsidiary if enrichment else None,
            "is_foreign_company": enrichment.is_foreign_company if enrichment else None,
            "fortune_company": enrichment.fortune_company if enrichment else None,

            "source": enrichment.source if enrichment else None,
        },
    })


@login_required
def my_companies(request):
    """Personal 'My Companies' page — every company the current user created
    (i.e. was the `owner_user` when the row was filed).

    Visible to consultants, franchise partners, coordinators, and business
    users. Read-only listing with status + location, plus a View action
    that hits the same company-detail drawer the rest of the app uses, so
    we don't have to reimplement the modal here.

    Superusers fall through to the standard Company Database page — they
    don't have a personal "my companies" perspective.
    """
    user = request.user
    if user.is_superuser:
        # No personal view for the platform admin — send them to the
        # global directory instead of a confusing empty page.
        return redirect("companies")

    role_code = (user.role.code or "").lower() if user.role else ""
    allowed_roles = {"consultant", "franchise", "coordinator", "business_user"}
    if role_code not in allowed_roles:
        raise PermissionDenied()

    qs = (
        Company.all_objects
        .filter(owner_user=user, is_deleted=False)
        .select_related("tenant", "consultant")
        .order_by("-created_at")
    )

    page_number = request.GET.get("page", 1)
    paginator = Paginator(qs, 10)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/my_companies.html",
        {
            "companies": page_obj,
            "page_obj": page_obj,
            "total_count": qs.count(),
            "active_menu": "my-companies",
        },
    )