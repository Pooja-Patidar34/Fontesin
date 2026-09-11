from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.shortcuts import render

from accounts.models import User
from accounts.utils.country_matching import country_match_q


def _coordinator_or_superuser(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_code = (user.role.code or "").upper() if user.role else ""
    return role_code == "COORDINATOR"


def _can_view_staff(user):
    """Coordinator, franchise partner, or superuser may view staff directories.

    Franchise partners are recognised by OWNERSHIP, not by role code. Buying a
    franchise is additive and leaves the account's role alone (see
    accounts.utils.franchise_access), so the holders in practice are
    ``business_user`` accounts that own an activated node. The sidebar already
    gates the Network menu on that ownership (`is_active_franchise_owner`);
    this check still only accepted the legacy ``FRANCHISE`` role code, so every
    holder saw the menu and got a 403 on all four pages behind it. The role
    code stays accepted for accounts that still carry it.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role_code = (user.role.code or "").upper() if user.role else ""
    if role_code in {"COORDINATOR", "FRANCHISE"}:
        return True

    from accounts.utils.franchise_access import is_franchise_holder
    return is_franchise_holder(user)


def _scoped_tenant_qs(qs, user, target_role=None):
    """Tenant scoping for non-superusers. Coordinators see every tenant —
    they oversee consultants across the platform — so the tenant filter is
    dropped for them. Everyone else stays pinned to their own tenant.

    Dropped for a franchise holder listing STAFF (consultants or coordinators)
    too. A franchise is a GEOGRAPHY and a TREE, not a tenant: the holder's node
    says "the USA" and owns a subtree, and the right scopes for that are the
    territory filter (coordinators) and the subtree filter (consultants) below,
    which answer exactly the question each tab asks. Pinning to the holder's own
    tenant on top of them silently subtracts every staff member who registered
    in a different tenant — in practice all of them, since a holder and a
    consultant or coordinator have no reason to share one — so the tab came up
    empty at every level, Master included (bug report, Sep 2026). Both filters
    fail closed on their own (a holder with no territory, or with nobody
    assigned under them, sees nobody), so nothing is left unscoped here.
    """
    if user.is_superuser:
        return qs
    role_code = (user.role.code or "").upper() if user.role else ""
    if role_code == "COORDINATOR":
        return qs

    if (target_role or "").upper() in {"COORDINATOR", "CONSULTANT"}:
        from accounts.utils.franchise_access import is_franchise_holder
        if is_franchise_holder(user):
            return qs

    return qs.filter(tenant=user.tenant)


def _scope_consultants_to_coordinator_region(qs, viewer, target_role):
    """Region scoping is currently disabled for coordinators viewing consultants:
    a coordinator sees every consultant in the system, regardless of region.
    Kept as a hook in case region-based scoping is reintroduced later."""
    return qs


def _scope_consultants_to_franchise_subtree(qs, viewer, target_role):
    """A franchise holder sees only the consultants inside their OWN subtree.

    Downward visibility (spec §7.1): the consultants assigned to the node(s)
    the holder owns, plus those assigned to every descendant node — and nothing
    from a parent or a parallel branch (§7.3). So a Master sees its own roster
    plus every sub-franchise's; a Micro sees only its own; and no holder ever
    sees the consultants their parent franchise assigned. Before this, a holder
    got every consultant in the tenant, i.e. effectively the whole platform.

    `subtree_consultant_ids` is the same node→consultant bridge the franchise
    reporting screens already use, so one definition of "under me" serves both.

    Deliberately unchanged for the other two audiences:
      • superuser — global visibility (§7.4), and they must also see
        consultants who are not assigned anywhere yet.
      • coordinator — oversees consultants platform-wide; that is what
        `_scope_consultants_to_coordinator_region` documents.
    """
    if target_role.upper() != "CONSULTANT":
        return qs
    if getattr(viewer, "is_superuser", False):
        return qs
    role_code = (viewer.role.code or "").upper() if viewer.role else ""
    if role_code == "COORDINATOR":
        return qs

    from accounts.utils.franchise_access import is_franchise_holder
    if not is_franchise_holder(viewer):
        # Not a holder and not staff — `_can_view_staff` already refused them,
        # so leave the queryset alone rather than inventing a third rule here.
        return qs

    # Imported inside the function: accounts.view.franchise pulls in a large
    # slice of the franchise stack, and importing it at module scope would make
    # these two view modules import each other.
    from accounts.view.franchise import subtree_consultant_ids
    return qs.filter(id__in=subtree_consultant_ids(viewer))


def _coordinator_country_q(code):
    """Match coordinators whose managed COUNTRY is `code` (an ISO alpha-2).

    Mirrors the priority chain `_coordinator_region_code` (accounts/view/
    company.py) uses to decide which region a coordinator actually manages, so
    this tab and the coordinator's own Company Database agree on where a
    coordinator sits:

      1. territory_country — the explicit ISO code, when an admin assigned one.
      2. target_region     — the country picked on the application form, stored
                             as a canonical English name (matched together with
                             the ISO code and known aliases via country_match_q).
      3. country           — the coordinator's own country, last resort.

    Each level is only consulted when the ones above it are blank, which is why
    the fallbacks carry the "…is blank" guards: a coordinator explicitly
    assigned to Germany must not also match Spain because they happen to live
    there.
    """
    no_territory = Q(territory_country__isnull=True) | Q(territory_country="")
    no_target = Q(target_region__isnull=True) | Q(target_region="")

    q = Q(territory_country__iexact=code)
    q |= no_territory & country_match_q(code, field="target_region")
    q |= no_territory & no_target & country_match_q(code, field="country")
    return q


def _coordinator_sub_level_q(value, territory_field, profile_field):
    """Match coordinators against one sub-country level (region or city).

    The coordinator's value for that level is `territory_<level>` when an admin
    assigned one, else the matching profile field (`state_region` / `city`).
    Registration requires a country, a state/region AND a city from every user
    (accounts/view/auth.py:register — they are in `required_fields`), so a
    coordinator always carries the profile pair even though the coordinator
    application form itself only asks for a country.

    The match is exact: a Regional over Madhya Pradesh lists the Madhya Pradesh
    coordinators and a Micro over Bhopal the Bhopal ones. A coordinator with no
    value at this level cannot be placed in that state or city and so does not
    appear — the tab answers "who is IN this territory", not "whose territory
    contains it".
    """
    territory_blank = Q(**{f"{territory_field}__isnull": True}) | Q(**{territory_field: ""})

    return (
        Q(**{f"{territory_field}__iexact": value})
        | (territory_blank & Q(**{f"{profile_field}__iexact": value}))
    )


def _scope_coordinators_to_franchise_territory(qs, viewer, target_role):
    """A franchise holder sees only the coordinators inside their OWN territory.

    "Same region as the franchise", level by level:

      Master   IN                  → every coordinator in India
      National IN                  → every coordinator in India
      Regional IN / Madhya Pradesh → the Madhya Pradesh coordinators
      Micro    IN / MP / Bhopal    → the Bhopal coordinators

    So each level narrows to exactly the territory the node holds. A level the
    NODE leaves blank is not constrained (a Master and a region-less National
    both name only a country, and match the whole of it); a level the node DOES
    name must be matched, so a coordinator whose own region is unknown or
    different is not listed. `_coordinator_sub_level_q` resolves the
    coordinator's side of that comparison.

    A holder whose nodes carry no territory at all sees nothing rather than
    everything: failing closed is the right default for a scoping rule.

    Deliberately unchanged for the other two audiences:
      • superuser — global visibility (§7.4).
      • coordinator — the platform-wide staff directory they already had.
    """
    if target_role.upper() != "COORDINATOR":
        return qs
    if getattr(viewer, "is_superuser", False):
        return qs
    role_code = (viewer.role.code or "").upper() if viewer.role else ""
    if role_code == "COORDINATOR":
        return qs

    from accounts.utils.franchise_access import (
        LIVE_STATUSES, is_franchise_holder, owned_franchise_nodes,
    )
    if not is_franchise_holder(viewer):
        return qs

    # LIVE_STATUSES (active + suspended) is the same set `is_franchise_holder`
    # gates on, so a suspended holder keeps the read-only view they already have.
    nodes = [
        n for n in owned_franchise_nodes(viewer, LIVE_STATUSES)
        if (n.territory_country or "").strip()
    ]
    if not nodes:
        return qs.none()

    territory_q = Q()
    for n in nodes:
        node_q = _coordinator_country_q((n.territory_country or "").strip().upper())
        if (n.territory_region or "").strip():
            node_q &= _coordinator_sub_level_q(
                n.territory_region.strip(), "territory_region", "state_region",
            )
        if (n.territory_city or "").strip():
            node_q &= _coordinator_sub_level_q(
                n.territory_city.strip(), "territory_city", "city",
            )
        territory_q |= node_q
    return qs.filter(territory_q)


def _franchise_links_for(users):
    """{user_id: {"assigned": [...], "owns": [...]}} for the given users.

    Feeds the "Franchise" block in the consultant detail modal so a holder can
    see which franchise a consultant is assigned to and which (if any) they own
    themselves — a Micro-Franchise owner is also a consultant (spec §9.1.2), so
    both lists can be non-empty for the same person.

    Built once per page (10 rows) with two queries rather than per row.
    """
    from accounts.models import ConsultantAssignment, Tenant
    from accounts.constants import ConsultantAssignmentStatus, FranchiseLevel

    user_ids = [u.id for u in users]
    links = {uid: {"assigned": [], "owns": []} for uid in user_ids}
    if not user_ids:
        return links

    level_labels = dict(FranchiseLevel.CHOICES)

    def _label(node):
        level = str(level_labels.get(node.franchise_level, node.franchise_level or ""))
        territory = ", ".join(
            p for p in (node.territory_city, node.territory_region, node.territory_country) if p
        )
        return f"{node.name} — {level}" + (f" ({territory})" if territory else "")

    assignments = (
        ConsultantAssignment.objects
        .filter(consultant_user_id__in=user_ids, status=ConsultantAssignmentStatus.ACTIVE)
        .select_related("franchise_node")
        .order_by("franchise_node__name")
    )
    for a in assignments:
        if a.franchise_node_id and a.consultant_user_id in links:
            links[a.consultant_user_id]["assigned"].append(_label(a.franchise_node))

    owned = (
        Tenant.objects
        .filter(owner_user_id__in=user_ids, franchise_level__isnull=False)
        .order_by("name")
    )
    for node in owned:
        if node.owner_user_id in links:
            links[node.owner_user_id]["owns"].append(_label(node))

    return links


def _render_companies_by_role(request, role_code, *, page_title, owner_label, active_submenu):
    """Every company a user of the given role is associated with.

    Users can be tied to a company in three ways:
      * picked an existing Company at /register/  → stored on
        User.primary_company / UserCompany
      * CREATED the company themselves            → stored on
        Company.owner_user (read for the Platform Admin only — see the
        grouping below)
      * typed a new company name at /apply/       → stored as free-text
        on User.applied_company_name (+ applied_country_of_incorporation etc.)

    Company.consultant is intentionally NOT one of them: it marks the consultant
    ASSIGNED to a company (set at certification approval too), not the owner, so
    reading it here would list every business user's company the consultant has
    certified.

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

    # Companies the consultant OWNS — Company.owner_user, the FK set to the
    # creator when a company is filed through the Company form
    # (accounts/view/company.py). Without this a consultant who signed up and
    # then created a company saw nothing here: the loop below only read
    # primary_company (the company they REGISTERED with) and UserCompany, so a
    # company they created themselves was invisible.
    #
    # Deliberately NOT Company.consultant. That FK is also set when a consultant
    # certifies someone else's company (certification_action claims the record),
    # so keying on it pulls in every business user's company the consultant ever
    # approved — 33 such rows in the current data — which is not what this tab
    # answers. Owner is the question here: whose company is it.
    #
    # Platform Admin only, for now. Every other audience (coordinator, franchise
    # holder) keeps exactly the rows it had, because their lists are narrowed by
    # territory / subtree rules that this bulk lookup does not consult — widening
    # them here would leak companies across franchise branches.
    #
    # Fetched once and grouped, rather than one query per consultant.
    owned_companies_by_owner = {}
    if request.user.is_superuser:
        from collections import defaultdict
        from accounts.models import Company as _Company

        owned_companies_by_owner = defaultdict(list)
        owned = (
            _Company.objects
            .filter(owner_user_id__in=[o.id for o in owners], is_deleted=False)
            .order_by("name")
        )
        for comp in owned:
            owned_companies_by_owner[comp.owner_user_id].append(comp)

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
                # Real Company PK — the admin Edit / Delete actions need it to
                # address the existing company endpoints. Applied rows below
                # carry id=None because no Company record exists for them.
                "id": str(comp.id),
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

        for comp in owned_companies_by_owner.get(c.id, ()):
            if comp.id in seen_company_ids:
                continue
            seen_company_ids.add(comp.id)
            _upsert(str(comp.id), _company_row(comp), label)

        # The free-text application row is a FALLBACK: it stands in only when no
        # real Company could be found for this consultant. Gated on the full
        # `seen_company_ids` (owned companies included) — a consultant who typed
        # "Chris Schmitt Photography" on /apply/ and now owns the registered
        # company of that name must not be listed twice, once per source.
        applied_name = (c.applied_company_name or "").strip()
        if applied_name and not seen_company_ids:
            _upsert(
                f"applied:{c.id}",
                {
                    "id": None,
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
        # Platform Admin only: surfaces Add / Edit / Delete on this directory.
        # The actions themselves reuse the Company Database endpoints, which
        # keep their own permission checks — this flag only decides whether the
        # buttons are drawn, so a non-admin sees exactly the page they had.
        "can_manage": request.user.is_superuser,
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


# `coordinator_companies` (Network → Coordinators Companies) was removed in
# Sep 2026: a coordinator oversees a TERRITORY, not a portfolio of companies, so
# the grid only ever showed the company they happened to register with. The
# Coordinators tab (`coordinator_users`) is the coordinator view that answers a
# real question, and it is territory-scoped per franchise level. Its route is
# gone too, so the page is unreachable rather than merely unlinked.
# `_render_companies_by_role` stays — `consultant_companies` still uses it.


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
    qs = _scoped_tenant_qs(qs, request.user, role_code)
    qs = _scope_consultants_to_coordinator_region(qs, request.user, role_code)
    qs = _scope_consultants_to_franchise_subtree(qs, request.user, role_code)
    qs = _scope_coordinators_to_franchise_territory(qs, request.user, role_code)

    # Search by name / email / company so admins can quickly find a user.
    # Match each whitespace-separated token against any of the fields (AND
    # across tokens, OR across fields) so a full-name query like "Bilbo Pytlik"
    # matches first_name "Bilbo" + last_name "Pytlik". A plain icontains on the
    # whole string would look for "Bilbo Pytlik" inside a single field and find
    # nothing.
    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        for token in search_query.split():
            qs = qs.filter(
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(email__icontains=token)
                | Q(primary_company__name__icontains=token)
            )

    qs = qs.order_by("first_name", "last_name")

    paginator = Paginator(qs, 10)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    # Which franchise each listed user is assigned to / owns, for the detail
    # modal. Resolved for the current page only, so the two extra queries do
    # not grow with the directory.
    franchise_links = _franchise_links_for(page_obj)

    def _row(u):
        row = _serialize_user(u)
        link = franchise_links.get(u.id) or {}
        row["franchise_assigned"] = link.get("assigned") or []
        row["franchise_owned"] = link.get("owns") or []
        return row

    context = {
        "users": page_obj,
        "users_json": [_row(u) for u in page_obj],
        "page_obj": page_obj,
        "active_menu": "network",
        "active_submenu": active_submenu,
        "page_title": page_title,
        "entity_label": entity_label,
        "search_query": search_query,
        "total_count": paginator.count,
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


@login_required
def business_users(request):
    """Consultant "Users" directory: every ACTIVE business user on the
    platform, filterable by first name, last name, email, and phone.

    Cross-tenant on purpose — a consultant works with business users across
    tenants. This is distinct from the consultant's "Certified Users" page
    (accounts.view.user.user_list), which is scoped to the companies the
    consultant has personally certified. Read-only listing with a View detail
    modal. Superusers may open it too (oversight / testing).
    """
    role_code = (request.user.role.code or "").lower() if request.user.role else ""
    if not (request.user.is_superuser or role_code == "consultant"):
        raise PermissionDenied()

    qs = (
        User.objects
        .select_related("role", "primary_company", "tenant")
        .filter(role__code__iexact="business_user", is_active=True, is_deleted=False)
    )

    # Single search box — each whitespace-separated token must match at least
    # one of first name / last name / email / phone (AND across tokens, OR
    # across fields). This lets "john gmail" match first name John + a gmail
    # address, while a single token like "john" or "555" still works.
    search_query = (request.GET.get("q") or "").strip()
    if search_query:
        for token in search_query.split():
            qs = qs.filter(
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(email__icontains=token)
                | Q(phone__icontains=token)
            )

    qs = qs.order_by("first_name", "last_name")

    page_number = request.GET.get("page", 1)
    paginator = Paginator(qs, 10)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        "users": page_obj,
        "users_json": [_serialize_user(u) for u in page_obj],
        "page_obj": page_obj,
        "active_menu": "business-users",
        "page_title": "Users",
        "entity_label": "business",
        "search_query": search_query,
        "total_count": paginator.count,
        # Platform Admin only: surfaces Add / Edit / Delete on this directory.
        # A consultant keeps the read-only listing described above. The actions
        # reuse the Users-page endpoints, which enforce their own permissions.
        "can_manage": request.user.is_superuser,
    }
    return render(request, "dashboard/business_users.html", context)
