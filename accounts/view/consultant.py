from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.shortcuts import render

from accounts.models import User


def _coordinator_or_superuser(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_code = (user.role.code or "").upper() if user.role else ""
    return role_code == "COORDINATOR"


def _can_view_staff(user):
    """Coordinator, franchise partner, or superuser may view staff directories."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_code = (user.role.code or "").upper() if user.role else ""
    return role_code in {"COORDINATOR", "FRANCHISE"}


def _scoped_tenant_qs(qs, user):
    """Tenant scoping for non-superusers. Coordinators see every tenant —
    they oversee consultants across the platform — so the tenant filter is
    dropped for them. Everyone else stays pinned to their own tenant."""
    if user.is_superuser:
        return qs
    role_code = (user.role.code or "").upper() if user.role else ""
    if role_code == "COORDINATOR":
        return qs
    return qs.filter(tenant=user.tenant)


def _scope_consultants_to_coordinator_region(qs, viewer, target_role):
    """Region scoping is currently disabled for coordinators viewing consultants:
    a coordinator sees every consultant in the system, regardless of region.
    Kept as a hook in case region-based scoping is reintroduced later."""
    return qs


def _render_companies_by_role(request, role_code, *, page_title, owner_label, active_submenu):
    """Every company a user of the given role is associated with.

    Users can be tied to a company in two ways:
      * picked an existing Company at /register/  → stored on
        User.primary_company / UserCompany / Company.consultant
      * typed a new company name at /apply/       → stored as free-text
        on User.applied_company_name (+ applied_country_of_incorporation etc.)

    We walk every user of the role and emit one row per (user, company) pairing,
    then dedupe by company identity.
    """
    owners = (
        User.objects
        .select_related("primary_company", "tenant")
        .prefetch_related("usercompany_set__company")
        .filter(role__code__iexact=role_code, is_deleted=False)
    )
    owners = _scoped_tenant_qs(owners, request.user)
    owners = _scope_consultants_to_coordinator_region(owners, request.user, role_code)

    rows = {}

    def _upsert(key, row, owner_name):
        existing = rows.get(key)
        if existing:
            if owner_name and owner_name not in existing["owners"]:
                existing["owners"].append(owner_name)
        else:
            row["owners"] = [owner_name] if owner_name else []
            rows[key] = row

    for c in owners:
        label = f"{c.first_name} {c.last_name}".strip() or c.email
        seen_company_ids = set()

        def _company_row(comp):
            return {
                "name": comp.name,
                "country": comp.country or "",
                "city": comp.city or "",
                "state": comp.state or "",
                "postal_code": comp.postal_code or "",
                "address_line1": comp.address_line1 or "",
                "address_line2": comp.address_line2 or "",
                "classification": comp.classification or "",
                "registration_id": comp.registration_id or "",
                "phone": comp.phone or "",
                "website": comp.website or "",
                "is_active": comp.is_active,
                "source": "registered",
            }

        if c.primary_company_id:
            comp = c.primary_company
            seen_company_ids.add(comp.id)
            _upsert(str(comp.id), _company_row(comp), label)

        for uc in c.usercompany_set.all():
            comp = uc.company
            if not comp or comp.id in seen_company_ids:
                continue
            seen_company_ids.add(comp.id)
            _upsert(str(comp.id), _company_row(comp), label)

        applied_name = (c.applied_company_name or "").strip()
        if applied_name and not seen_company_ids:
            _upsert(
                f"applied:{c.id}",
                {
                    "name": applied_name,
                    "country": c.applied_country_of_incorporation or "",
                    "city": "",
                    "state": "",
                    "postal_code": "",
                    "address_line1": "",
                    "address_line2": "",
                    "classification": c.applied_legal_form or "",
                    "registration_id": c.applied_company_reg_number or "",
                    "phone": "",
                    "website": c.applied_company_website or "",
                    "year_founded": c.applied_year_founded,
                    "num_employees": c.applied_num_employees or "",
                    "is_active": True,
                    "source": "applied",
                },
                label,
            )

    companies_list = sorted(rows.values(), key=lambda r: r["name"].lower())

    page_number = request.GET.get("page", 1)
    paginator = Paginator(companies_list, 10)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        "companies": page_obj,
        "companies_json": list(page_obj),
        "page_obj": page_obj,
        "active_menu": "network",
        "active_submenu": active_submenu,
        "page_title": page_title,
        "owner_label": owner_label,
    }
    return render(request, "dashboard/consultant_companies.html", context)


@login_required
def consultant_companies(request):
    """Companies associated with consultant users, scoped to the tenant."""
    if not _can_view_staff(request.user):
        raise PermissionDenied()
    return _render_companies_by_role(
        request,
        "CONSULTANT",
        page_title="Consultants' Companies",
        owner_label="Consultants",
        active_submenu="consultant-companies",
    )


@login_required
def coordinator_companies(request):
    """Companies associated with coordinator users, scoped to the tenant."""
    if not _can_view_staff(request.user):
        raise PermissionDenied()
    return _render_companies_by_role(
        request,
        "COORDINATOR",
        page_title="Coordinators' Companies",
        owner_label="Coordinators",
        active_submenu="coordinator-companies",
    )


def _serialize_user(u):
    return {
        # Identity
        "id": str(u.id),
        "first_name": u.first_name or "",
        "last_name": u.last_name or "",
        "email": u.email,
        "is_active": u.is_active,

        # Contact
        "phone": u.phone or "",
        "national_prefix": u.national_prefix or "",
        "linkedin_url": u.linkedin_url or "",

        # Personal
        "birth_date": u.birth_date.isoformat() if u.birth_date else "",
        "gender": u.gender or "",
        "ethnicity": u.ethnicity or "",
        "preferred_language": u.preferred_language or "",
        "nationality": u.nationality or "",
        "bio": u.bio or "",
        "notes": u.notes or "",
        "photo_url": u.photo_url or "",

        # Address
        "country": u.country or "",
        "city": u.city or "",
        "state_region": u.state_region or "",
        "postal_code": u.postal_code or "",
        "address_line1": u.address_line1 or "",
        "address_line2": u.address_line2 or "",

        # Territory (coordinator assignment)
        "territory_country": u.territory_country or "",
        "territory_region": u.territory_region or "",
        "territory_city": u.territory_city or "",

        # Professional
        "current_position": u.current_position or "",
        "years_of_experience": u.years_of_experience or "",
        "primary_industry": u.primary_industry or "",
        "professional_summary": u.professional_summary or "",

        # Company (registered)
        "company": u.primary_company.name if u.primary_company else "",

        # Company (applied)
        "applied_company_name": u.applied_company_name or "",
        "applied_company_reg_number": u.applied_company_reg_number or "",
        "applied_country_of_incorporation": u.applied_country_of_incorporation or "",
        "applied_legal_form": u.applied_legal_form or "",
        "applied_year_founded": u.applied_year_founded,
        "applied_num_employees": u.applied_num_employees or "",
        "applied_company_website": u.applied_company_website or "",

        # Application
        "target_region": u.target_region or "",
        "franchise_type": u.franchise_type or "",
        "motivation": u.motivation or "",
        "network_connections": u.network_connections or "",
        "expected_companies": u.expected_companies or "",
        "reference_1": u.reference_1 or "",
        "reference_2": u.reference_2 or "",
        "application_status": u.application_status or "",

        # Role metadata
        "consultant_sub_role": u.consultant_sub_role or "",
        "subscription_plan": u.subscription_plan or "",

        # System
        "created_at": u.created_at.isoformat() if u.created_at else "",
        "updated_at": u.updated_at.isoformat() if u.updated_at else "",
    }


def _render_users_by_role(request, role_code, *, page_title, entity_label, active_submenu):
    page_number = request.GET.get("page", 1)

    qs = (
        User.objects
        .select_related("role", "primary_company", "tenant")
        .filter(role__code__iexact=role_code, is_deleted=False)
    )
    qs = _scoped_tenant_qs(qs, request.user)
    qs = _scope_consultants_to_coordinator_region(qs, request.user, role_code)
    qs = qs.order_by("first_name", "last_name")

    paginator = Paginator(qs, 10)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        "users": page_obj,
        "users_json": [_serialize_user(u) for u in page_obj],
        "page_obj": page_obj,
        "active_menu": "network",
        "active_submenu": active_submenu,
        "page_title": page_title,
        "entity_label": entity_label,
    }
    return render(request, "dashboard/consultant_users.html", context)


@login_required
def consultant_users(request):
    """Every User whose role is CONSULTANT, scoped to the tenant."""
    if not _can_view_staff(request.user):
        raise PermissionDenied()
    return _render_users_by_role(
        request,
        "CONSULTANT",
        page_title="Consultant Users",
        entity_label="consultant",
        active_submenu="consultant-users",
    )


@login_required
def coordinator_users(request):
    """Every User whose role is COORDINATOR, scoped to the tenant."""
    if not _can_view_staff(request.user):
        raise PermissionDenied()
    return _render_users_by_role(
        request,
        "COORDINATOR",
        page_title="Coordinator Users",
        entity_label="coordinator",
        active_submenu="coordinator-users",
    )
