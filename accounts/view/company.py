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
from billing.utils import PLAN_REGIONS, _region_for_country, get_user_geographic_scope


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


def _coordinator_region_code(user):
    """Resolve the ISO country code of the region a coordinator manages.

    Priority:
      1. territory_country — an explicit ISO code, if an admin assigned one.
      2. target_region     — the region the coordinator picked on the
                             application form. It's stored as a country *label*
                             (e.g. "United States"), so we map it back to its
                             ISO code via the CountryChoices labels + aliases.
      3. country           — the coordinator's own country (ISO code), as a
                             last-resort fallback.

    Returns the ISO code (e.g. "US") or "" when none can be determined.
    """
    territory_country = (user.territory_country or "").strip().upper()
    if territory_country:
        return territory_country

    target_region = (user.target_region or "").strip()
    if target_region:
        label_to_code = {lbl.lower(): code for code, lbl in CountryChoices.CHOICES}
        code = label_to_code.get(target_region.lower())
        if code:
            return code
        # Free-text region spellings (e.g. "USA") map through the same alias
        # table used to match Company.country.
        for c, aliases in _COUNTRY_ALIASES.items():
            if target_region.lower() in {a.lower() for a in aliases}:
                return c

    return (user.country or "").strip().upper()


def coordinator_territory_q(user):
    """Region scope for a coordinator's company access.

    A coordinator oversees a whole territory, so they should see every active
    company in the region they manage (e.g. the USA coordinator sees all USA
    companies) — not just the handful they're directly linked to. The managed
    region is resolved by _coordinator_region_code (territory_country →
    target_region → country).

    Company.country is free-text while the resolved region is an ISO code, so
    we match across the code + label + common aliases via _country_match_q.
    Returns None when the user isn't a coordinator or no region can be
    determined, so callers can skip widening the scope (a coordinator with no
    region info keeps their linked-company view rather than getting the entire
    directory).
    """
    role_code = (user.role.code or "").lower() if user.role else ""
    if role_code != "coordinator":
        return None

    region_code = _coordinator_region_code(user)
    if not region_code:
        return None

    scope_q = _country_match_q(region_code) & Q(is_active=True)

    # State / city narrowing only applies to an explicitly-assigned
    # territory_country — target_region and country are country-level only.
    territory_country = (user.territory_country or "").strip().upper()
    if territory_country:
        territory_region = (user.territory_region or "").strip()
        if territory_region:
            scope_q &= Q(state__iexact=territory_region)

        territory_city = (user.territory_city or "").strip()
        if territory_city:
            scope_q &= Q(city__iexact=territory_city)

    return scope_q


def business_user_plan_scope_q(user):
    """Discovery-scope Q for a business user's Company Database list.

    Visibility (which companies show in the list) by plan:

        free   → ALL active companies worldwide (read-only: no View/Connect)
        basic  → selected country
        pro    → region (group of countries, e.g. North America = US/CA/MX)
        global → worldwide

    Free plan deliberately sees the whole directory so users can browse what's
    available before upgrading — but they get no actual access: the View
    button stays locked (requires an approved connection) and Connect is a
    paid-only action, so a free user can never open company details. The
    paid tiers' geographic scope comes from the canonical billing model
    (billing.utils.get_user_geographic_scope).

    The billing scope yields ISO codes; Company.country is free-text, so each
    code is matched across its code + CountryChoices label + common aliases
    via _country_match_q.

    Returns None when the plan grants no discovery scope — no plan at all, or
    a country/region plan where the user hasn't set a country yet. Callers OR
    this with their linkage query, so None keeps the user's linked-company
    view rather than widening it to the whole directory.
    """
    # Free plan: companies in the user's REGISTERED country only, shown with a
    # limited set of fields and no actions (read-only teaser — see the row /
    # header templates gated on is_free_plan). Country is the only location
    # signal captured at sign-up (User.country, an ISO code), matched across
    # code + label + aliases via _country_match_q. No country set → no discovery
    # scope (the user keeps their linkage-only view).
    plan_code = _plan_code_for_business_user(user)
    if plan_code == "free":
        country = (getattr(user, "country", "") or "").strip()
        if not country:
            return None
        return _country_match_q(country) & Q(is_active=True)

    scope = get_user_geographic_scope(user)
    mode = scope.get("mode")

    if mode == "worldwide":
        return Q(is_active=True)

    if mode == "none":
        return None

    # mode == "country" or "region": match every code in the allowed set.
    countries = [c for c in (scope.get("countries") or []) if c]
    if not countries:
        return None

    country_q = Q()
    for code in countries:
        country_q |= _country_match_q(code)
    return country_q & Q(is_active=True)


def editable_companies_qs(user):
    """Companies `user` is allowed to WRITE to (edit / toggle / delete).

    This is intentionally narrower than the view scope. A business user may
    edit ONLY the company they created (owner_user) — per the product rule
    "edit your own company, not others". Their primary company created by
    someone else, partner companies linked via UserCompany, and discovery
    rows are all view-only for them. Consultants / coordinators / franchise
    keep the broader linkage write scope (companies they consult for, own, or
    are linked to). Superusers and tenant admins are handled separately by
    callers (all companies / tenant-wide).
    """
    role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
    if role_code == "business_user":
        return Company.objects.filter(owner_user=user)
    return Company.objects.filter(
        Q(consultant=user)
        | Q(owner_user=user)
        | Q(primary_users=user)
        | Q(usercompany__user=user)
    ).distinct()


def consultant_certification_scope_q(user):
    """Q matching the pending companies in a consultant's certification queue.

    A certification request is broadcast to every active consultant: the
    company is saved `certification_status="pending"`, `is_active=False`, and
    usually `consultant=NULL` until one consultant approves it (which claims
    ownership). Until then those rows fall outside the normal linkage scope, so
    a consultant can neither View nor Edit them from the Certifications page —
    the deep-link detail fetch 404s and the modal never opens.

    This returns the same scope the Certifications queue itself uses
    (certification.py): pending + (unclaimed OR claimed by this consultant).
    Returns None for non-consultants so callers can skip widening their scope.
    """
    role_code = (user.role.code or "").lower() if getattr(user, "role", None) else ""
    if role_code != "consultant":
        return None
    return Q(certification_status="pending") & (
        Q(consultant__isnull=True) | Q(consultant=user)
    )


def companies_editable_via_form(user):
    """Companies a user may open + save in the Company edit modal.

    Extends editable_companies_qs with the consultant's certification queue so
    a consultant can Edit a pending request from the Certifications page (the
    "Edit company details, then come back to approve" action) before approving
    it. Business users stay owner-only; other roles keep their linkage scope.

    Scoped to the edit modal on purpose — toggle/delete keep the narrower
    editable_companies_qs so a pending row can't be flipped active outside the
    approve flow.
    """
    base = editable_companies_qs(user)
    cert_q = consultant_certification_scope_q(user)
    if cert_q is None:
        return base
    return Company.objects.filter(Q(pk__in=base.values("pk")) | cert_q).distinct()


def business_user_visible_companies(user):
    """Companies a business user can see in their Company Database list.

    Mirrors the gating used in `company_list` so anything that needs the
    same scope (Users page, future Reports) can ask for it without copy-
    pasting the linkage + plan-discovery query. Returns a queryset; the
    caller decides how to consume it. Returns an empty queryset for
    non-business-users (superusers/tenant admins should never call this).
    """
    plan_code = _plan_code_for_business_user(user)
    if plan_code is None:
        return Company.objects.none()

    linkage_q = (
        Q(consultant=user)
        | Q(owner_user=user)
        | Q(primary_users=user)
        | Q(usercompany__user=user)
    )

    # Discovery scope by plan (see business_user_plan_scope_q):
    #   free   → all active companies worldwide (read-only)
    #   basic  → selected country
    #   pro    → region (group of countries)
    #   global → worldwide
    # Read-only restrictions for free plan (View / Connect / Edit) are still
    # applied by the templates via is_free_plan.
    scope_q = business_user_plan_scope_q(user)

    full_q = linkage_q if scope_q is None else (linkage_q | scope_q)
    return Company.objects.filter(full_q).distinct()
from accounts.utils.ip import get_client_ip
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.template.loader import render_to_string

from accounts.forms.company_form import CompanyForm


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


# Origin pages that open the edit modal as a deep link (?open_edit=&from=).
# Kept in sync with the ORIGIN_PATHS map in companies.html.
_DEEP_EDIT_ORIGIN_PATHS = {
    "my-companies": "/my-companies/",
    "certifications": "/certifications/",
}


def _safe_post_redirect(next_url):
    """Resolve where to send the user after a successful create/update POST.

    The edit modal is opened as a deep link via
    ?open_edit=<id>&from=<origin>, and the form's hidden `next` field carries
    that same full path. Redirecting straight back to it re-triggers the
    auto-open JS in companies.html, so the modal pops right back up after a
    save — which reads as "the request didn't go through" (the My Companies
    "Request Certification" loop). When `open_edit` is present we instead send
    the user back to the page they came from (My Companies / Certifications),
    falling back to the bare Company Database list. Any other `next` URL is
    returned untouched.

    Returns a path string, or None when there's no usable next URL (caller
    falls back to the "companies" route name).
    """
    if not next_url:
        return None

    from urllib.parse import urlparse, parse_qs

    params = parse_qs(urlparse(next_url).query)
    if "open_edit" not in params:
        return next_url

    origin = (params.get("from", [""])[0] or "").lower()
    return _DEEP_EDIT_ORIGIN_PATHS.get(origin) or "/companies/"


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
                # Write scope is role-aware (see editable_companies_qs):
                # business users may edit ONLY the company they created
                # (owner_user) — not their primary company created by someone
                # else, not partner companies, not the rest of the directory.
                # Consultants / coordinators / franchise keep the broader
                # linkage write scope. We deliberately never match on
                # Q(tenant=...) here: business users share the "Default" tenant
                # with most companies, so a tenant match would let any business
                # user edit every company in that tenant. Tenant admins
                # (handled above) keep tenant-wide edit.
                # companies_editable_via_form also lets a consultant open + save
                # a pending request from their Certifications queue (Edit button).
                company = get_object_or_404(
                    companies_editable_via_form(request.user),
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

            # Enforce tenant safety: a non-superuser's company always belongs to
            # their own tenant. Some accounts (e.g. consultants onboarded without
            # one) have no tenant — fall back to the platform "Default" tenant
            # (then any active tenant) so creation doesn't fail on the NOT NULL
            # Company.tenant column with an unhelpful "Could not save" error.
            if not request.user.is_superuser:
                company.tenant = (
                    request.user.tenant
                    or Tenant.objects.filter(name__iexact="Default", is_active=True).first()
                    or Tenant.objects.filter(is_active=True).order_by("created_at").first()
                )

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
            # vetted — flag them as awaiting consultant certification and hold
            # them out of the public directory until approved. The request is
            # broadcast to every active consultant; the first one to approve
            # claims ownership of the record (consultant FK is set at approval
            # time in certification_action). Consultants who create companies
            # for their own clients bypass this gate. Platform admins
            # (superusers) also bypass — anything they file is treated as
            # authoritative and goes straight into the company directory,
            # auto-certified by the admin who created it.
            emit_cert_notification = False
            resubmitted_for_certification = False
            if not company_id and request.user.is_superuser:
                from django.utils import timezone
                company.certification_status = "certified"
                company.certified_by = request.user
                company.certified_at = timezone.now()
            elif not company_id and creator_role_code != "consultant":
                company.certification_status = "pending"
                company.is_active = False
                emit_cert_notification = True
            elif (
                company_id
                and creator_role_code == "business_user"
                and request.POST.get("request_certification")
                and (company.certification_status or "").lower() != "certified"
            ):
                # Business user edited a not-yet-certified company and clicked
                # the dedicated "Request Certification" button (the plain "Save"
                # button omits this flag and just persists the edits without
                # touching certification). Covers every non-certified state —
                # "uncertified" (incl. blank/legacy rows that only DISPLAY as
                # Uncertified), "rejected" resubmissions after a decline, AND
                # "pending" (the BU updated their details and wants to re-send
                # the request). Push it into the certification queue as a FRESH,
                # unclaimed pending request (clearing any prior consultant claim)
                # so every active consultant is (re)notified. Already-certified
                # companies are excluded — there's nothing to request.
                company.certification_status = "pending"
                company.is_active = False
                company.consultant = None
                company.certified_by = None
                company.certified_at = None
                emit_cert_notification = True
                resubmitted_for_certification = True

            company.save()
            form.save_m2m()

            # Link the new company as the business user's primary company when
            # they don't have one yet. The Company Database modal previously
            # set only owner_user, so a company created here showed up under
            # "My Companies" (owner_user) but never on the user's Profile page,
            # which reads primary_company. Mirrors the profile Create-Company
            # flow so both entry points leave the same linkage. Scoped to
            # business users — a consultant creating a client's company must
            # not have it become their own primary company.
            if (
                not company_id
                and creator_role_code == "business_user"
                and not request.user.primary_company_id
            ):
                from accounts.models import UserCompany
                request.user.primary_company = company
                request.user.save(update_fields=["primary_company"])
                UserCompany.objects.get_or_create(
                    user=request.user,
                    company=company,
                    defaults={"is_primary": True},
                )

            if emit_cert_notification:
                try:
                    from accounts.utils.notifications import notify_certification_request
                    notify_certification_request(company, submitted_by=request.user)
                except Exception:
                    pass

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

            if resubmitted_for_certification:
                success_msg = "Certification request sent successfully. A consultant will review your company shortly."
            elif company_id:
                success_msg = "Company updated successfully."
            elif request.user.is_superuser or creator_role_code == "consultant":
                success_msg = "Company created successfully."
            else:
                success_msg = "Certification request submitted. A consultant will review your company shortly."

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
            return redirect(_safe_post_redirect(next_url) or "companies")

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
        role_code = (request.user.role.code or "").lower() if request.user.role else ""
        if role_name == "tenant_admin":
            # Tenant admins see every company in their tenant.
            queryset = Company.objects.filter(tenant=request.user.tenant)
        elif role_code == "consultant":
            # Consultants get full visibility into the active company database
            # across the whole system — every active (is_active=True), non-
            # deleted company, not just the ones they're personally linked to
            # as consultant/owner. The location filter bar (enabled for
            # consultants below) lets them narrow this down, and the "own
            # first" ordering still floats their linked companies to the top.
            queryset = Company.objects.filter(is_active=True)
        else:
            # Everyone else (business_user, coordinator, franchise)
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

            # Coordinator discovery scope: on top of the companies they're
            # directly linked to, a coordinator sees every active company in
            # the region they manage. See coordinator_territory_q for details.
            coordinator_scope_q = coordinator_territory_q(request.user)
            if coordinator_scope_q is not None:
                linkage_q = linkage_q | coordinator_scope_q

            # Business-user discovery scope, by plan (see
            # business_user_plan_scope_q):
            #   free   → all active companies worldwide (read-only)
            #   basic  → selected country
            #   pro    → region (group of countries, e.g. North America)
            #   global → all active companies worldwide
            # The "no details" / read-only restriction for free plan is applied
            # by the row templates via is_free_plan, not here.
            #
            # The billing scope yields ISO codes; Company.country is free-text,
            # so each code is matched across code + label + aliases inside
            # business_user_plan_scope_q. It returns None when the plan grants
            # no discovery scope (no plan, or no country set on a country/region
            # plan), in which case the user keeps their linkage-only view.
            scope_q = business_user_plan_scope_q(request.user)

            if scope_q is not None:
                # Business users discover all ACTIVE companies in their plan
                # scope — certified and uncertified alike (scope_q already pins
                # is_active=True). Certified companies are active too, so they're
                # included. Their OWN + joined companies also show via linkage_q.
                linkage_q = linkage_q | scope_q

            queryset = Company.objects.filter(linkage_q).distinct()

            # Coordinators see ALL active companies in their region — both
            # certified and uncertified — per product decision (mirrors the
            # business-user rule that active companies should be visible
            # regardless of certification). The region scope (coordinator_
            # territory_q) already constrains to is_active=True in their
            # territory, so no extra certification filter is applied here.

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

    # Global free-text search box (shown to the admin in the Company Database
    # header). Token-based so a multi-word query like "sona private" matches
    # companies containing both words, and each token may hit the name,
    # registration id, classification, or location. Applied on top of whatever
    # role scoping produced `queryset`, so a non-superuser could only ever
    # search within companies they're already allowed to see.
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        for token in search_q.split():
            queryset = queryset.filter(
                Q(name__icontains=token)
                | Q(registration_id__icontains=token)
                | Q(classification__icontains=token)
                | Q(city__icontains=token)
                | Q(country__icontains=token)
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
    # Join-request state (separate from the Connect/partnership flow above) so
    # the "Join" action can flip to "Join requested" / "Joined" on rows the BU
    # has already acted on. pending_join_ids = pending CompanyJoinRequest;
    # member_company_ids = companies they're already a member of (UserCompany).
    pending_join_ids = set()
    member_company_ids = set()
    # Compute connection state for any BU (free / basic / pro / global) so the
    # Connect button can flip to "Connection requested" / "Connected" on rows
    # the user has already acted on. Previously this was gated to paid BUs
    # only, which meant free-plan users always saw a fresh "Connect" button
    # even after sending a request.
    if role_code == "business_user":
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

        from accounts.models import CompanyJoinRequest, UserCompany
        pending_join_ids = set(
            CompanyJoinRequest.objects
            .filter(
                user=request.user,
                status=CompanyJoinRequest.STATUS_PENDING,
                company_id__in=page_company_ids,
            )
            .values_list("company_id", flat=True)
        )
        member_company_ids = set(
            UserCompany.objects
            .filter(user=request.user, company_id__in=page_company_ids)
            .values_list("company_id", flat=True)
        )

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
    _role_code = (request.user.role.code or "").lower() if request.user.role else ""

    # Deep-link edit: when a user clicks "Edit" from My Companies or the
    # Certifications queue, we land here with ?open_edit=<id>&from=<origin>
    # so the modal can pop without the surrounding Company Database UI being
    # visible. Keep the sidebar highlighted on the origin so it doesn't feel
    # like the user navigated away from their starting page.
    _origin = (request.GET.get("from") or "").strip().lower()
    _active_menu = "companies"
    if request.GET.get("open_edit"):
        if _origin == "my-companies":
            _active_menu = "my-companies"
        elif _origin == "certifications":
            _active_menu = "certifications"

    context = {
        "companies": page_obj,
        "page_obj": page_obj,
        "tenants": tenants,
        "selected_tenant_id": selected_tenant_id,
        "form": form,
        "can_manage": has_permission(request.user, "company.manage"),
        "can_view": has_permission(request.user, "company.view"),
        "active_menu": _active_menu,
        "next": request.get_full_path(),
        "applied_filters": applied_filters,
        "search_q": search_q,
        "pending_ids": pending_ids,
        "accepted_ids": accepted_ids,
        "pending_join_ids": pending_join_ids,
        "member_company_ids": member_company_ids,
        "viewable_ids": viewable_ids,
        # Surface BU role to the modal so it can render the
        # "Maintained by consultant" helper text on the contact-name inputs.
        "is_business_user": not request.user.is_superuser and _role_code == "business_user",
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
    # FETCH COMPANY (WRITE-SCOPED)
    # -------------------------------
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
        # Deleting is a write — restrict to the role-aware write scope so a
        # business user can only delete the company they created (owner_user),
        # never another company that happens to share their "Default" tenant.
        company = get_object_or_404(
            editable_companies_qs(request.user),
            id=company_id,
        )

    company_name = company.name
    tenant = company.tenant

    # -------------------------------
    # DELETE (soft)
    # -------------------------------
    # Soft-delete rather than a hard DB delete. A hard delete fails with a
    # ProtectedError when the company has protected references such as
    # ConsultantCommission rows (payout history must not be destroyed). The
    # Company model is built for soft deletion: `objects` (ActiveManager)
    # excludes is_deleted=True, and the unique-name constraint is scoped to
    # is_deleted=False so the name is freed for reuse. So flagging is_deleted
    # removes the company from every active view while preserving its financial
    # / audit records.
    company.is_deleted = True
    company.is_active = False
    company.save(update_fields=["is_deleted", "is_active", "updated_at"])

    # Detach the deleted company from users so it disappears EVERYWHERE it's read
    # via a direct FK/M2M — e.g. the profile "My Company" panel reads
    # primary_company directly (list views already filter is_deleted). Users
    # whose primary company was this one are reset to no primary (they'll see the
    # Set-Up / Join prompt). UserCompany membership rows are removed too. The
    # owner / consultant / certified_by FKs are left intact for the audit +
    # commission trail.
    from accounts.models import User as _User, UserCompany as _UserCompany
    _User.objects.filter(primary_company=company).update(primary_company=None)
    _UserCompany.objects.filter(company=company).delete()

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
    role_code = (request.user.role.code or "").lower() if request.user.role else ""

    if request.user.is_superuser:
        company = get_object_or_404(Company, id=company_id)
    elif role_name == "tenant_admin":
        company = get_object_or_404(
            Company,
            id=company_id,
            tenant=request.user.tenant,
        )
    elif role_code == "consultant":
        # Consultants have full visibility into the company database (see the
        # company_list scoping), so they can also activate/deactivate any
        # company from the list — not just the ones they're directly linked
        # to. Without this they got a 404 toggling an unlinked company they
        # could nonetheless see. Default manager resolves both active and
        # inactive (non-deleted) rows so reactivation works too.
        company = get_object_or_404(Company, id=company_id)
    else:
        # Match the edit-path scoping (editable_companies_qs): activating /
        # deactivating is a write, so a business user may only toggle the
        # company they created (owner_user) — never a partner company or
        # another company that shares their "Default" tenant. Coordinators /
        # franchise keep the broader linkage write scope.
        company = get_object_or_404(
            editable_companies_qs(request.user),
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

        # Coordinators can View any company in the region they manage, to
        # match the territory scope applied to their Company Database list.
        coordinator_scope_q = coordinator_territory_q(request.user)
        if coordinator_scope_q is not None:
            scope_q = scope_q | coordinator_scope_q

        # Consultants can View a pending request from their Certifications
        # queue (broadcast/unclaimed or claimed by them) so the Edit deep-link
        # can load the modal — those rows are is_active=False with
        # consultant=NULL until approval and otherwise fall outside the scope.
        cert_scope_q = consultant_certification_scope_q(request.user)
        if cert_scope_q is not None:
            scope_q = scope_q | cert_scope_q

        # Paid business users (basic / pro / global) can View any company in
        # their plan discovery scope — the always-on "View" button in the list
        # would otherwise 404 here for companies they aren't directly linked to.
        # Mirrors the list scoping: all ACTIVE companies in scope (bu_scope_q
        # already pins is_active=True). Free plan stays limited to linked/
        # connected companies.
        plan_code = _plan_code_for_business_user(request.user)
        if plan_code in ("basic", "pro", "global"):
            bu_scope_q = business_user_plan_scope_q(request.user)
            if bu_scope_q is not None:
                scope_q = scope_q | bu_scope_q

        company = get_object_or_404(
            Company.objects.filter(scope_q).distinct(),
            id=company_id,
        )

    enrichment = getattr(company, "enrichment", None)

    # Whether the requesting user may edit the contact-person fields
    # (First/Last name + Contact Email). Mirrors the CompanyForm gate: a
    # business user can only edit the contact person on a company they OWN —
    # on any other company those fields belong to the owner / certifying
    # consultant. Staff (superuser / tenant admin) and consultants keep edit
    # rights. The modal JS uses this to lock the inputs + show the
    # "Maintained by the certifying consultant" hint on companies the BU
    # doesn't own. The server-side form is the real enforcement; this just
    # keeps the UI honest.
    _role_code = (request.user.role.code or "").lower() if request.user.role else ""
    _is_business_user = not request.user.is_superuser and _role_code == "business_user"
    _is_owner = company.owner_user_id == request.user.id
    can_edit_contact = (not _is_business_user) or _is_owner

    # Companies created by a consultant don't go through the certification
    # queue (there's no admin/consultant flow to certify them), so the modal
    # should not show a certification-status pill for them. Flagged here off the
    # owner's role so the frontend can hide the badge.
    _owner = company.owner_user
    owner_is_consultant = bool(
        _owner and _owner.role_id and (getattr(_owner.role, "code", "") or "").lower() == "consultant"
    )

    return JsonResponse({
        # --------------------
        # Company (Core)
        # --------------------
        "company": {
            "id": str(company.id),
            "tenant": str(company.tenant.id),
            "can_edit_contact": can_edit_contact,
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
            "contact_first_name": company.contact_first_name or "",
            "contact_last_name": company.contact_last_name or "",

            # Absolute URL so the template can render the logo in the modal
            # header regardless of how the page was opened (e.g. via API or
            # an internal redirect).
            "logo_url": request.build_absolute_uri(company.logo.url) if company.logo else None,
            "certification_status": company.certification_status,
            # True when the company was created by a consultant — certification
            # doesn't apply, so the modal hides the status pill.
            "owner_is_consultant": owner_is_consultant,
            "certified_by_name": (
                (f"{company.certified_by.first_name} {company.certified_by.last_name}".strip()
                 or company.certified_by.email)
                if company.certified_by else None
            ),
            "certified_at": company.certified_at.isoformat() if company.certified_at else None,

            # Certifying consultant snapshot for the read-only "Certifying
            # Consultant" panel. Sourced live from the User FK so the panel
            # auto-refreshes when the consultant updates their profile — no
            # backfill required on the Company row.
            "certifying_consultant": (
                {
                    "first_name": company.certified_by.first_name or "",
                    "last_name": company.certified_by.last_name or "",
                    "full_name": (
                        f"{company.certified_by.first_name} {company.certified_by.last_name}".strip()
                        or company.certified_by.email
                    ),
                    "email": company.certified_by.email,
                    "phone": company.certified_by.phone or "",
                }
                if company.certified_by else None
            ),

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
    """Personal 'My Companies' page — companies the current user created
    (``owner_user``) plus companies they've JOINED and been approved for
    (linked via UserCompany, e.g. an approved profile join request or an
    accepted partnership).

    Visible to consultants, franchise partners, coordinators, and business
    users. Read-only listing with status + location, plus a View action
    that hits the same company-detail drawer the rest of the app uses, so
    we don't have to reimplement the modal here. The Edit action is shown
    only for companies the user owns — joined companies are read-only for
    business users.

    Superusers fall through to the standard Company Database page — they
    don't have a personal "my companies" perspective.
    """
    from accounts.models import UserCompany

    user = request.user
    if user.is_superuser:
        # No personal view for the platform admin — send them to the
        # global directory instead of a confusing empty page.
        return redirect("companies")

    role_code = (user.role.code or "").lower() if user.role else ""
    allowed_roles = {"consultant", "franchise", "coordinator", "business_user"}
    if role_code not in allowed_roles:
        raise PermissionDenied()

    # Companies the user owns OR is a member of (UserCompany link). distinct()
    # collapses the row a user owns AND has a UserCompany link for.
    joined_ids = UserCompany.objects.filter(user=user).values_list("company_id", flat=True)
    qs = (
        Company.all_objects
        .filter(Q(owner_user=user) | Q(id__in=list(joined_ids)), is_deleted=False)
        .select_related("tenant", "consultant")
        .distinct()
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
            # Gates the "Add Company" button — same permission the Company
            # Database page uses to show its create action.
            "can_manage": has_permission(request.user, "company.manage"),
            # Context for the in-page "Add Company" modal (shared create flow
            # with the Company Database page). The form POSTs to the
            # `companies` endpoint; on success the page reloads so the new row
            # renders in this page's own format.
            "form": CompanyForm(user=user),
            "country_states": COUNTRY_STATES,
            "is_business_user": role_code == "business_user",
            # Superusers never reach this view (redirected above), so there's
            # no tenant picker to seed — keep these blank for the modal markup.
            "tenants": [],
            "selected_tenant_id": "",
            # Non-AJAX fallback target after a successful create.
            "next": request.get_full_path(),
        },
    )