"""Franchise request → approve → activate workflow (spec §2, §14, §16).

The franchise tree is layered onto the Tenant model (a Tenant row with a
`franchise_level` is a franchise node). Users never self-assign a franchise
role: they submit a FranchiseApplication for a target level + territory, it
routes to the Super Admin queue, and only after the Super Admin approves AND
activates (contract + payment) does a Tenant node go ACTIVE and grant the
holder the Franchises section. Self-activation is impossible by construction —
the applicant is never the approver.

Mirrors the coordinator-request / application-review flows so the queue, the
badges, and the notifications all behave the same way.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _, ngettext

from accounts.constants import (
    ConsultantAssignmentStatus,
    ConsultantType,
    ContractStatus,
    CountryChoices,
    COUNTRY_STATES,
    FranchiseApplicationStatus,
    FranchiseFeeStatus,
    FranchiseLevel,
    FranchiseUnitStatus,
)
from accounts.models import (
    AuditLog,
    Company,
    ConsultantAssignment,
    FranchiseApplication,
    FranchiseRemovalRequest,
    Tenant,
    User,
)
from accounts.utils.franchise_access import (
    franchise_manager_required,
    is_franchise_holder,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_ip(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _audit(request, node, action, **metadata):
    """Record an immutable audit row for a franchise action (spec Rule 10).

    AuditLog.tenant is required and a franchise node IS a Tenant, so the node
    scopes its own audit trail. Never let auditing break the action."""
    try:
        AuditLog.objects.create(
            tenant=node,
            actor=request.user if request.user.is_authenticated else None,
            action=action,
            entity_type="franchise_node",
            entity_id=node.id,
            metadata=metadata or {},
            ip_address=_client_ip(request),
        )
    except Exception:
        pass


def _audit_application(request, application, action, **metadata):
    """Record an audit row for an application-level action that has no franchise
    node yet — a rejection (spec Rule 11 'audit all critical actions').

    AuditLog.tenant is required, but a rejected application never created a node.
    Attach the row to the routed parent franchise (a Tenant) when there is one
    (sub-franchise requests), otherwise to the applicant's own tenant (Master
    requests). If neither exists, skip silently — auditing never breaks the flow."""
    tenant = application.parent_franchise or getattr(application.applicant_user, "tenant", None)
    if tenant is None:
        return
    try:
        AuditLog.objects.create(
            tenant=tenant,
            actor=request.user if request.user.is_authenticated else None,
            action=action,
            entity_type="franchise_application",
            entity_id=application.id,
            metadata=metadata or {},
            ip_address=_client_ip(request),
        )
    except Exception:
        pass


def _unique_node_name(base):
    """Tenant.name is globally unique — derive a free name from `base`."""
    name = base
    counter = 1
    while Tenant.all_objects.filter(name=name).exists():
        counter += 1
        name = f"{base} ({counter})"
    return name


def _territory_label(country, region, city, local_area):
    # CountryChoices labels are lazy translation proxies — coerce to str before
    # joining so the derived node name is a plain string.
    country_label = str(dict(CountryChoices.CHOICES).get((country or "").upper(), country or ""))
    parts = [local_area, city, region, country_label]
    return ", ".join(str(p) for p in parts if (p or "").strip())


def parent_chain_basic(node):
    """Basic, non-sensitive identity data for a node's parent chain (spec §10.2 /
    Rule 6 'Limited upward visibility').

    Returns only the columns the §10.2 table marks *allowed* — parent name,
    level, territory, contact person, relationship status — for each ancestor
    from the immediate parent up to the root. It deliberately exposes NO parent
    business data (sales, plans, performance, consultant rosters), so a holder
    can see the Master/National/Regional structure it operates under and nothing
    more."""
    chain = []
    for anc in node.get_ancestors():
        owner = anc.owner_user
        contact = ""
        if owner:
            contact = f"{owner.first_name} {owner.last_name}".strip() or owner.email
        chain.append({
            "name": anc.name,
            "level": anc.get_franchise_level_display(),
            "territory": _territory_label(
                anc.territory_country, anc.territory_region,
                anc.territory_city, anc.territory_local_area,
            ),
            "contact_person": contact,
            "relationship_status": anc.get_franchise_status_display(),
        })
    return chain


def _owns_any_node(user):
    return Tenant.objects.filter(
        owner_user=user, franchise_level__isnull=False
    ).exists()


def _requesting_company(request):
    """The company a franchise request is bought for — the one the applicant is
    currently acting as in the company switcher.

    A Business User with several companies buys each franchise for a specific
    company, so the node ends up attributed to it. Returns None for applicants
    with no company at all (consultants, coordinators)."""
    company_id = (request.POST.get("applicant_company") or "").strip()
    owned = Company.objects.filter(owner_user=request.user)
    if company_id:
        chosen = owned.filter(id=company_id).first()
        if chosen is not None:
            return chosen
    from billing.utils import resolve_active_company
    return resolve_active_company(request.user)


def visible_node_ids(user):
    """Franchise node ids `user` is allowed to see (spec §7).

    Superuser / Platform Admin → the whole tree (global visibility, §7.4).
    A franchise holder → their own node(s) plus every descendant (downward
    visibility, §7.1), and nothing on a parallel branch (§7.3). Everyone else
    → nothing."""
    if getattr(user, "is_superuser", False):
        return set(
            Tenant.objects.filter(franchise_level__isnull=False)
            .values_list("id", flat=True)
        )
    ids = set()
    for node in Tenant.objects.filter(owner_user=user, franchise_level__isnull=False):
        ids |= node.get_descendant_ids(include_self=True)
    return ids


def visible_nodes_qs(user):
    """Tenant queryset of franchise nodes visible to `user` (see
    `visible_node_ids`)."""
    return Tenant.objects.filter(
        id__in=visible_node_ids(user), franchise_level__isnull=False
    )


def subtree_consultant_ids(user, node_ids=None):
    """User ids of consultants actively assigned to any node in `user`'s visible
    franchise subtree (spec §7 downward visibility).

    This is the bridge from a franchise node to the business data attributed to
    it: a franchise "owns" the certified companies and plan sales made by the
    consultants operating under it or under any of its descendants. Pass
    `node_ids` to reuse an already-computed subtree (e.g. after filtering)."""
    if node_ids is None:
        node_ids = visible_node_ids(user)
    return set(
        ConsultantAssignment.objects.filter(
            franchise_node_id__in=node_ids,
            status=ConsultantAssignmentStatus.ACTIVE,
        ).values_list("consultant_user_id", flat=True)
    )


def _paginate(request, items, per_page=12):
    """Small paginator helper mirroring the consultant directory views."""
    paginator = Paginator(items, per_page)
    try:
        return paginator, paginator.page(request.GET.get("page", 1))
    except (PageNotAnInteger, EmptyPage):
        return paginator, paginator.page(1)


def _paginate_named(request, items, param, per_page=10):
    """Paginate `items` using a per-list query param (e.g. 'approved_page'), so a
    tabbed page can paginate each tab independently. Returns the Page object."""
    paginator = Paginator(items, per_page)
    try:
        return paginator.page(request.GET.get(param, 1))
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


# Statuses that make a node "occupy" its territory — it holds the exclusive
# right, so no second franchise of the same level+territory may be approved.
# Only TERMINATED / EXPIRED (or soft-deleted) free the territory up again.
OCCUPYING_STATUSES = [
    FranchiseUnitStatus.PENDING_CONTRACT,
    FranchiseUnitStatus.PENDING_PAYMENT,
    FranchiseUnitStatus.ACTIVE,
    FranchiseUnitStatus.SUSPENDED,
]


# Rejection reasons are short, applicant-facing notes — same 200-char budget the
# applicant gets for their own request note. The textarea caps this client-side;
# this is the server-side guard for anything that bypasses the form.
BOARD_NOTE_MAX = 200


def canonical_territory(level, country, region, city, local_area):
    """Reduce a territory to the granularity its level actually occupies, so
    'one franchise per territory+level' compares the right fields:

      Master   → country
      National → country + optional region/state
      Regional → country + region/state
      Micro    → country + region + city (+ optional local area)

    National may name a region/state but isn't required to (product decision,
    Jul 2026): a National with a region is exclusive within that state, one
    without stays country-wide. Only a Master is strictly country-only, so
    region is trimmed for Master alone. Trimming the deeper fields means a stray
    city typed on a Regional request can't slip a duplicate past
    territory_conflict(). Returns a normalised
    (country, region, city, local_area) tuple."""
    # Collapse internal whitespace (and trim) so cosmetically-different spellings
    # of the same place — "Ganga Ghat" vs "Ganga  Ghat" — normalise to one value.
    # Without this, the exclusivity check (territory_conflict) and the Micro DB
    # constraint compare the raw strings and let a whitespace-only duplicate slip
    # through. `" ".join(s.split())` splits on any run of whitespace and rejoins
    # with single spaces.
    country = (country or "").strip().upper()[:2]
    region = " ".join((region or "").split())[:120]
    city = " ".join((city or "").split())[:120]
    local_area = " ".join((local_area or "").split())[:120]
    rank = FranchiseLevel.RANK.get(level, 0)
    if rank < FranchiseLevel.RANK[FranchiseLevel.NATIONAL]:
        region = ""  # Master is country-only; National and deeper may carry a region.
    if rank < FranchiseLevel.RANK[FranchiseLevel.MICRO]:
        city = ""
        local_area = ""
    return country, region, city, local_area


def canonical_region(country, region):
    """Validate a state/region against the country's known subdivisions.

    If the country has a subdivision list (COUNTRY_STATES), return the canonical
    spelling that matches `region` case-insensitively, or None when it doesn't
    match any (so the caller can reject it). For a country with no list, region
    is free-text — return it unchanged. Mirrors the client-side dropdown so a
    stale/direct POST can't smuggle in an unknown region."""
    states = COUNTRY_STATES.get((country or "").strip().upper())
    if not states:
        return (region or "").strip()
    r = (region or "").strip().lower()
    for s in states:
        if s.lower() == r:
            return s
    return None


def territory_conflict(level, country, region, city, local_area, exclude_node_id=None):
    """Return the franchise node that already holds this level+territory, or None
    (spec §11.1 — one franchise per territory+level). Considers active + in-flight
    (pending/suspended) nodes so a second applicant can't be approved into a
    territory that's already taken or being set up."""
    # Match the whitespace/case normalisation used when territories are stored
    # (canonical_territory), so "Ganga Ghat" and "Ganga  Ghat" resolve to the
    # same territory here too — otherwise a whitespace-only duplicate reads as a
    # free territory. `__iexact` covers case; `" ".join(split())` covers spacing.
    qs = Tenant.objects.filter(
        franchise_level=level,
        franchise_status__in=OCCUPYING_STATUSES,
        territory_country=(country or "").strip().upper(),
        territory_region__iexact=" ".join((region or "").split()),
        territory_city__iexact=" ".join((city or "").split()),
        territory_local_area__iexact=" ".join((local_area or "").split()),
    ).select_related("owner_user")
    if exclude_node_id:
        qs = qs.exclude(id=exclude_node_id)
    return qs.first()


def _application_conflict(application):
    """The existing franchise (if any) that already holds the territory+level an
    application is requesting."""
    return territory_conflict(
        application.requested_level,
        application.requested_country,
        application.requested_region,
        application.requested_city,
        application.requested_local_area,
        exclude_node_id=application.created_franchise_id,
    )


def _territory_scope_word(level):
    """The territory noun a level occupies — used to word the 'already taken'
    message ('this state…', 'this city…') instead of a vague 'this territory'."""
    return {
        FranchiseLevel.MASTER: _("country"),
        FranchiseLevel.NATIONAL: _("country"),
        FranchiseLevel.REGIONAL: _("state / region"),
        FranchiseLevel.MICRO: _("city"),
    }.get(level, _("territory"))


def _territory_taken_reason(conflict):
    level_label = dict(FranchiseLevel.CHOICES).get(conflict.franchise_level, conflict.franchise_level)
    return _("This %(scope)s already has an active %(level)s (%(name)s), so it can't be granted twice.") % {
        "scope": _territory_scope_word(conflict.franchise_level),
        "level": level_label,
        "name": conflict.name,
    }


def resolve_parent_node(level, country, region, city, local_area):
    """Find the DIRECT parent for a requested sub-franchise (spec §4.2).

    The direct parent is the deepest ACTIVE franchise node whose tier is
    shallower than the requested level and whose territory contains the
    requested territory. Returns None for a Master request (no parent) or when
    no active ancestor covers the territory yet."""
    if level == FranchiseLevel.MASTER:
        return None
    req_rank = FranchiseLevel.RANK.get(level, 0)
    probe = Tenant(
        territory_country=country, territory_region=region,
        territory_city=city, territory_local_area=local_area,
    )
    best = None
    for candidate in Tenant.objects.filter(
        franchise_level__isnull=False, franchise_status=FranchiseUnitStatus.ACTIVE
    ):
        cand_rank = FranchiseLevel.RANK.get(candidate.franchise_level, 0)
        if cand_rank >= req_rank:
            continue  # parent must sit above the child in the tree
        if probe.is_territory_within(candidate):
            if best is None or cand_rank > FranchiseLevel.RANK.get(best.franchise_level, 0):
                best = candidate  # keep the deepest (closest) ancestor
    return best


def _create_node_from_application(application, parent, reviewer, now,
                                  *, node_name=None, contract_status=None,
                                  fee_status=None):
    """Create the franchise node for an approved application (PENDING_CONTRACT).

    Shared by the Platform Admin (Master applications) and the direct-parent
    operational reviewer (sub-franchise applications). Validates the tree
    invariants before saving; raises ValidationError on a bad tree so callers
    can surface a friendly message. Returns the saved node.

    The Add Sub-Franchise flow (spec §8.1) passes `node_name` (the proposed
    legal / company name) and the initial `contract_status` / `fee_status` the
    holder recorded; the other flows omit them and get the defaults (a derived
    name, PENDING contract, UNPAID fee). The node is always PENDING_CONTRACT
    regardless — only the Platform Admin's activation flips it to ACTIVE (§5)."""
    applicant = application.applicant_user
    applicant_label = (
        f"{applicant.first_name} {applicant.last_name}".strip() or applicant.email
    )
    level_label = dict(FranchiseLevel.CHOICES).get(
        application.requested_level, application.requested_level
    )
    # A Master covers the whole country — never a region/city (spec §3.1).
    is_master = application.requested_level == FranchiseLevel.MASTER
    t_region = "" if is_master else application.requested_region
    t_city = "" if is_master else application.requested_city
    t_local = "" if is_master else application.requested_local_area
    territory = _territory_label(
        application.requested_country, t_region, t_city, t_local,
    )
    base_name = (node_name or "").strip() or f"{level_label} — {territory or applicant_label}"
    node = Tenant(
        name=_unique_node_name(base_name),
        franchise_level=application.requested_level,
        franchise_status=FranchiseUnitStatus.PENDING_CONTRACT,
        contract_status=contract_status or ContractStatus.PENDING,
        franchise_fee_status=fee_status or FranchiseFeeStatus.UNPAID,
        is_exclusive=(application.requested_level == FranchiseLevel.MICRO),
        parent=parent,
        owner_user=applicant,
        # The company that bought it (My Franchises groups nodes by company).
        owner_company=application.applicant_company,
        territory_country=application.requested_country,
        territory_region=t_region,
        territory_city=t_city,
        territory_local_area=t_local,
        approved_by=reviewer,
        approved_at=now,
        created_by=reviewer,
    )
    node.clean()  # may raise ValidationError
    node.save()

    application.application_status = FranchiseApplicationStatus.APPROVED
    application.approved_by = reviewer
    application.approved_at = now
    application.parent_franchise = parent
    application.created_franchise = node
    application.save(update_fields=[
        "application_status", "approved_by", "approved_at",
        "parent_franchise", "created_franchise", "updated_at",
    ])
    return node


# ---------------------------------------------------------------------------
# Applicant side
# ---------------------------------------------------------------------------

@login_required
def franchise_request_view(request):
    """The applicant's page: submit a franchise request and track its status,
    plus an overview of any franchises they already hold (spec §12 'My
    Franchise', minimal)."""
    if request.user.is_superuser:
        # The Super Admin manages franchises from the review queue, not here.
        return redirect("franchise-applications")

    # Any authenticated non-superuser account may request a franchise — Business
    # Users, Consultants, Coordinators alike (product decision, Jul 2026). The
    # request routes to the Super Admin queue; the applicant's current role has
    # no bearing on eligibility, and on activation the holder is granted the
    # franchise role like any other applicant.

    applications = (
        FranchiseApplication.objects.filter(applicant_user=request.user)
        .select_related("parent_franchise", "created_franchise", "approved_by", "rejected_by")
        .order_by("-created_at")
    )
    owned = list(
        Tenant.objects.filter(owner_user=request.user, franchise_level__isnull=False)
        .select_related("parent", "parent__owner_user", "owner_user", "owner_company")
        .order_by("name")
    )
    # Limited upward visibility (spec §10.2 / Rule 6): expose only the allowed
    # basic identity data about each owned node's parent chain — never parent
    # business data.
    open_removals = {
        r.node_id: r for r in FranchiseRemovalRequest.objects.filter(
            requested_by=request.user, status=FranchiseRemovalRequest.PENDING,
        )
    }
    for n in owned:
        n.parent_chain = parent_chain_basic(n)
        # Giving up a franchise needs the granting authority's approval, so each
        # card shows either the request action or the decision it's waiting on.
        n.open_removal = open_removals.get(n.id)
        reviewer_node = _removal_reviewer_node(n)
        n.removal_reviewer_name = reviewer_node.name if reviewer_node else ""

    removal_history = list(
        FranchiseRemovalRequest.objects.filter(requested_by=request.user)
        .exclude(status=FranchiseRemovalRequest.PENDING)
        .select_related("node", "reviewer_franchise")
        .order_by("-decided_at")[:20]
    )

    has_open = applications.filter(
        application_status__in=FranchiseApplicationStatus.OPEN
    ).exists()

    # Holding a franchise no longer closes this form. A holder may buy further
    # franchises anywhere in the world that is still available — one per
    # company they own, in different countries — so the form stays open and the
    # holder simply sees their existing franchises alongside it. The only
    # territories they can't buy here are the ones under their OWN node; those
    # are added as sub-franchise proposals (guarded in the submit view).
    is_franchise_holder = bool(owned)

    # The company a new franchise would be bought for. A Business User picks
    # among the companies they own; everyone else has none and the node is
    # simply held by the user.
    from billing.utils import resolve_active_company
    owned_companies = list(
        Company.objects.filter(owner_user=request.user).order_by("name")
    )
    active_company = resolve_active_company(request.user)

    # Territories already held (active or in-flight) at each level, so the form
    # can warn the applicant the moment they pick a taken territory — without a
    # round-trip. The server-side guard in franchise_request_submit is the
    # authority; this is purely a nicer, earlier UX. Match the exact-territory,
    # same-level rule of territory_conflict() and normalise so the client can
    # compare case-insensitively.
    taken_territories = []
    for n in Tenant.objects.filter(
        franchise_level__isnull=False,
        franchise_status__in=OCCUPYING_STATUSES,
    ):
        c_country, c_region, c_city, c_local = canonical_territory(
            n.franchise_level, n.territory_country, n.territory_region,
            n.territory_city, n.territory_local_area,
        )
        taken_territories.append({
            "level": n.franchise_level,
            "level_label": str(dict(FranchiseLevel.CHOICES).get(n.franchise_level, n.franchise_level)),
            "scope": str(_territory_scope_word(n.franchise_level)),
            "country": c_country,
            "region": c_region.lower(),
            "city": c_city.lower(),
            "local_area": c_local.lower(),
            "name": n.name,
        })

    # Values from a rejected submit (if any), popped so they only pre-fill once.
    form_data = request.session.pop("franchise_request_form", None) or {}

    return render(
        request,
        "dashboard/franchise_request.html",
        {
            "active_menu": "franchise-request",
            "applications": applications,
            "owned_franchises": owned,
            "has_open_application": has_open,
            "is_franchise_holder": is_franchise_holder,
            "owned_companies": owned_companies,
            "active_company": active_company,
            "removal_history": removal_history,
            "level_choices": FranchiseLevel.CHOICES,
            "country_choices": CountryChoices.CHOICES,
            "taken_territories_json": json.dumps(taken_territories),
            # Country -> subdivisions for the State/Region dropdown (falls back
            # to free text for countries not in the map).
            "country_states": COUNTRY_STATES,
            # Repopulate the form after a validation-error redirect.
            "form_data": form_data,
            "form_data_json": json.dumps(form_data),
        },
    )


@login_required
@require_POST
@transaction.atomic
def franchise_request_submit(request):
    """Applicant submits a franchise request. Routes to the Super Admin queue."""
    if request.user.is_superuser:
        raise PermissionDenied("The Super Admin does not request franchises.")

    # Any authenticated non-superuser may request a franchise (Business Users,
    # Consultants, Coordinators, etc.). The Super Admin reviews and gates the
    # request; role is not an eligibility criterion.

    # Preserve what the applicant typed so a validation-error redirect can
    # repopulate the form instead of wiping it (cleared on success below).
    request.session["franchise_request_form"] = {
        k: (request.POST.get(k) or "") for k in (
            "requested_level", "requested_country", "requested_region",
            "requested_city", "requested_local_area", "application_note",
        )
    }

    level = (request.POST.get("requested_level") or "").strip().upper()
    if level not in dict(FranchiseLevel.CHOICES):
        messages.error(request, _("Please choose a valid franchise level."))
        return redirect("franchise-request")

    country = (request.POST.get("requested_country") or "").strip().upper()[:2]
    region = (request.POST.get("requested_region") or "").strip()[:120]
    city = (request.POST.get("requested_city") or "").strip()[:120]
    local_area = (request.POST.get("requested_local_area") or "").strip()[:120]
    note = (request.POST.get("application_note") or "").strip()[:200]

    if not country:
        messages.error(request, _("Please select the target country for the franchise."))
        return redirect("franchise-request")

    # Reduce the territory to what this level actually occupies (Master = country,
    # National = country + optional state, Regional = + required state, Micro =
    # + city). This makes a Master correctly contain every sub-franchise beneath
    # it and stops a stray deeper field from slipping a duplicate past the
    # one-per-territory check below.
    country, region, city, local_area = canonical_territory(
        level, country, region, city, local_area
    )

    # Territory granularity required per level (mirrors the form's dynamic
    # required-field markers): a Regional must name its region/state, a Micro
    # must name both its region and city. Master is country-only; National may
    # name a region/state but doesn't have to.
    if level in (FranchiseLevel.REGIONAL, FranchiseLevel.MICRO) and not region:
        messages.error(request, _("Please enter the region / state for this franchise level."))
        return redirect("franchise-request")
    if level == FranchiseLevel.MICRO and not city:
        messages.error(request, _("Please enter the city for a Micro-Franchise."))
        return redirect("franchise-request")

    # The region must be a real subdivision of the country when one is required
    # (free-text is allowed only for countries without a known subdivision list).
    if region:
        canon = canonical_region(country, region)
        if canon is None:
            messages.error(request, _("Please choose a valid state / region for the selected country."))
            return redirect("franchise-request")
        region = canon

    # One franchise per territory+level (spec §11.1). If an active/in-flight
    # franchise already holds this exact territory at this level, there is nothing
    # to approve — tell the applicant up front instead of queueing a request that
    # can only be rejected. (The template also blocks this client-side; this is
    # the authoritative guard against direct/stale POSTs.)
    conflict = territory_conflict(level, country, region, city, local_area)
    if conflict is not None:
        messages.error(request, _territory_taken_reason(conflict))
        return redirect("franchise-request")

    # A holder may buy franchises in several territories, so several requests can
    # be in flight at once — but not two for the SAME level + territory, which
    # would queue a request that can only be rejected.
    if FranchiseApplication.objects.filter(
        applicant_user=request.user,
        application_status__in=FranchiseApplicationStatus.OPEN,
        requested_level=level,
        requested_country=country,
        requested_region=region,
        requested_city=city,
        requested_local_area=local_area,
    ).exists():
        messages.info(
            request,
            _("You already have a request under review for this territory. Please wait for the decision."),
        )
        return redirect("franchise-request")

    # Approval routing (spec §4.2): a Master request goes to the Platform Admin;
    # a sub-franchise request routes to its DIRECT parent franchise (the deepest
    # active ancestor covering the territory), which is the operational reviewer.
    parent = resolve_parent_node(level, country, region, city, local_area)
    if level != FranchiseLevel.MASTER and parent is None:
        messages.error(
            request,
            _("No active parent franchise covers this territory yet. A higher-level "
              "franchise must be active before you can request a sub-franchise here."),
        )
        return redirect("franchise-request")

    # You can't become your own franchisee: a territory that falls under a node
    # this user already holds is added from their own Franchises section as a
    # sub-franchise proposal, not bought through this form.
    if parent is not None and parent.owner_user_id == request.user.id:
        messages.info(
            request,
            _("This territory sits under your own franchise %(name)s. Add it from "
              "your Franchises section as a sub-franchise instead.") % {"name": parent.name},
        )
        return redirect("franchise-request")

    application = FranchiseApplication.objects.create(
        applicant_user=request.user,
        applicant_company=_requesting_company(request),
        requested_level=level,
        requested_country=country,
        requested_region=region,
        requested_city=city,
        requested_local_area=local_area,
        parent_franchise=parent,
        application_note=note,
        application_status=FranchiseApplicationStatus.SUBMITTED,
    )

    # Audit the submission (spec §14 'Application submitted').
    _audit_application(
        request, application, "franchise.submitted",
        application_id=str(application.id),
        requested_level=level,
        territory=_territory_label(country, region, city, local_area),
        status=application.application_status,
    )

    try:
        from accounts.utils.notifications import notify_franchise_application_submitted
        notify_franchise_application_submitted(application)
    except Exception:
        pass

    # Submitted cleanly — drop the preserved form values so the form comes back
    # empty rather than pre-filled with the just-submitted request.
    request.session.pop("franchise_request_form", None)

    if parent is not None:
        messages.success(
            request,
            _("Your request has been submitted to %(parent)s for review.") % {"parent": parent.name},
        )
    else:
        messages.success(
            request,
            _("Your franchise request has been submitted. The Platform Admin will review it shortly."),
        )
    return redirect("franchise-request")


# ---------------------------------------------------------------------------
# Super Admin side
# ---------------------------------------------------------------------------

@login_required
def franchise_applications_list(request):
    """Platform Admin queue (spec §4.2).

    Operationally reviews MASTER applications (Pending tab) and is the final
    activation authority for EVERY approved franchise (Awaiting Activation),
    including sub-franchises approved by their parent."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    base = FranchiseApplication.objects.select_related(
        "applicant_user", "parent_franchise", "parent_franchise__owner_user",
        "created_franchise", "approved_by", "rejected_by"
    )
    # Master applications are the Platform Admin's operational responsibility.
    pending = list(base.filter(
        application_status__in=FranchiseApplicationStatus.OPEN,
        parent_franchise__isnull=True,
    ).order_by("-created_at"))
    for app in pending:
        app.conflict = _application_conflict(app)
    # Sub-franchise requests are routed to their direct parent for operational
    # review, but the Platform Admin sees them all here too and can step in to
    # approve/reject (admin override) when the parent hasn't acted (spec §4.2).
    pending_sub = list(base.filter(
        application_status__in=FranchiseApplicationStatus.OPEN,
        parent_franchise__isnull=False,
    ).order_by("-created_at"))
    for app in pending_sub:
        app.conflict = _application_conflict(app)
    # Everything approved (Master or sub) — the full approved history.
    approved = base.filter(
        application_status=FranchiseApplicationStatus.APPROVED
    ).order_by("-approved_at")
    # Focused sub-list: approved nodes still awaiting the Admin's activation
    # (contract + payment) — a dedicated tab so activations aren't buried in the
    # full Approved history (spec §5).
    awaiting_activation = list(base.filter(
        application_status=FranchiseApplicationStatus.APPROVED,
        created_franchise__franchise_status__in=[
            FranchiseUnitStatus.PENDING_CONTRACT,
            FranchiseUnitStatus.PENDING_PAYMENT,
        ],
    ).order_by("-approved_at"))
    rejected = base.filter(
        application_status=FranchiseApplicationStatus.REJECTED
    ).order_by("-rejected_at")

    # Holders giving up a franchise: the Admin decides Master (and orphaned)
    # exits; sub-franchise exits are their direct parent's call and show there.
    removal_pending = list(pending_removal_requests_for(request.user).order_by("-created_at"))
    removal_decided = list(
        FranchiseRemovalRequest.objects
        .exclude(status=FranchiseRemovalRequest.PENDING)
        .select_related("node", "requested_by", "reviewer_franchise", "decided_by")
        .order_by("-decided_at")[:50]
    )

    # Total counts drive the tab badges (before pagination trims each list).
    counts = {
        "pending": len(pending),
        "sub": len(pending_sub),
        "awaiting": len(awaiting_activation),
        "approved": approved.count(),
        "rejected": rejected.count(),
        "removals": len(removal_pending),
    }
    # Each tab paginates independently via its own query param (e.g. approved_page).
    pending = _paginate_named(request, pending, "pending_page")
    pending_sub = _paginate_named(request, pending_sub, "sub_page")
    awaiting_activation = _paginate_named(request, awaiting_activation, "awaiting_page")
    approved = _paginate_named(request, approved, "approved_page")
    rejected = _paginate_named(request, rejected, "rejected_page")

    return render(
        request,
        "dashboard/franchise_applications.html",
        {
            "active_menu": "franchise-applications",
            "pending": pending,
            "pending_sub": pending_sub,
            "awaiting_activation": awaiting_activation,
            "approved": approved,
            "rejected": rejected,
            "counts": counts,
            "removal_pending": removal_pending,
            "removal_decided": removal_decided,
            "removal_next": "franchise-applications",
        },
    )


@login_required
@require_POST
@transaction.atomic
def franchise_application_action(request, application_id):
    """Platform Admin approves/rejects a franchise application (spec §4.2).

    Handles MASTER applications (the Admin's own operational responsibility) and
    — as an override — sub-franchise applications that are normally reviewed by
    their direct parent. The Admin can step in on a sub-request the parent hasn't
    acted on; when it's approved here the node is created under that same parent,
    exactly as if the parent had approved it."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "reject"):
        messages.error(request, _("Invalid action."))
        return redirect("franchise-applications")

    application = get_object_or_404(
        FranchiseApplication.objects.filter(
            application_status__in=FranchiseApplicationStatus.OPEN,
        ),
        id=application_id,
    )
    # A sub-franchise keeps its routed parent; a Master has none. Approving here
    # builds the node under whatever parent the request was routed to.
    parent = application.parent_franchise
    now = timezone.now()

    if decision == "reject":
        board_note = (request.POST.get("board_note") or "").strip()[:BOARD_NOTE_MAX]
        if not board_note:
            # Auto-explain "territory already taken" so the applicant learns why.
            conflict = _application_conflict(application)
            if conflict:
                board_note = _territory_taken_reason(conflict)
        application.application_status = FranchiseApplicationStatus.REJECTED
        application.rejected_by = request.user
        application.rejected_at = now
        application.board_note = board_note
        application.save(update_fields=[
            "application_status", "rejected_by", "rejected_at", "board_note", "updated_at",
        ])
        _audit_application(request, application, "franchise.rejected",
                           application_id=str(application.id),
                           requested_level=application.requested_level,
                           status=application.application_status, note=board_note,
                           parent_id=str(parent.id) if parent else None)
        _notify_decision(application, approved=False)
        messages.success(
            request,
            _("Rejected the franchise request from %(email)s.") % {
                "email": application.applicant_user.email
            },
        )
        return redirect("franchise-applications")

    # Exclusivity (spec §11.1): one franchise per territory+level. If the
    # territory is already held, don't approve a duplicate — reject it instead.
    conflict = _application_conflict(application)
    if conflict:
        messages.error(
            request,
            _("Can't approve — %(reason)s Reject this request instead.")
            % {"reason": _territory_taken_reason(conflict)},
        )
        return redirect("franchise-applications")

    # --- Approve: create the node in PENDING_CONTRACT under its routed parent
    # (None for a Master → top of tree). ---
    try:
        node = _create_node_from_application(application, parent=parent, reviewer=request.user, now=now)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("franchise-applications")

    if parent is None:
        _audit(request, node, "franchise.approved",
               application_id=str(application.id), level=node.franchise_level,
               status=application.application_status, note=application.board_note)
    else:
        # An admin override of the parent's operational review — record who the
        # parent was so the trail shows the Admin acted in the parent's stead.
        _audit(request, node, "franchise.admin_approved",
               application_id=str(application.id), level=node.franchise_level,
               status=application.application_status, note=application.board_note,
               parent_id=str(parent.id))
        try:
            from accounts.utils.notifications import notify_franchise_awaiting_activation
            notify_franchise_awaiting_activation(node)
        except Exception:
            pass
    _notify_decision(application, approved=True)

    messages.success(
        request,
        _("Approved %(name)s. It's now pending contract & payment — activate it once those are done.")
        % {"name": node.name},
    )
    return redirect("franchise-applications")


# ---------------------------------------------------------------------------
# Direct-parent (Master / National / Regional) operational review — spec §4.2
# ---------------------------------------------------------------------------

def _reviewer_parent_ids(user):
    """Active franchise nodes owned by `user` — the nodes for which they are the
    direct-parent operational reviewer of incoming sub-franchise requests."""
    return list(
        Tenant.objects.filter(
            owner_user=user,
            franchise_level__isnull=False,
            franchise_status=FranchiseUnitStatus.ACTIVE,
        ).values_list("id", flat=True)
    )


@login_required
def franchise_child_requests(request):
    """A franchise holder's queue of sub-franchise requests routed to their
    node(s) as the direct parent (spec §4.2 'Operational Reviewer')."""
    parent_ids = _reviewer_parent_ids(request.user)
    base = FranchiseApplication.objects.filter(
        parent_franchise_id__in=parent_ids
    ).select_related("applicant_user", "parent_franchise", "created_franchise")

    pending = list(base.filter(
        application_status__in=FranchiseApplicationStatus.OPEN
    ).order_by("-created_at"))
    # Flag requests whose territory+level is already held, so the reviewer knows
    # to reject the duplicate (spec §11.1).
    for app in pending:
        app.conflict = _application_conflict(app)
    approved = base.filter(
        application_status=FranchiseApplicationStatus.APPROVED
    ).order_by("-approved_at")[:50]
    rejected = base.filter(
        application_status=FranchiseApplicationStatus.REJECTED
    ).order_by("-rejected_at")[:50]

    # Holders below this one asking to give up their franchise land in the same
    # queue — the direct parent is the authority for both directions.
    removal_pending = list(pending_removal_requests_for(request.user).order_by("-created_at"))
    removal_decided = list(
        FranchiseRemovalRequest.objects.filter(
            reviewer_franchise_id__in=parent_ids,
        ).exclude(status=FranchiseRemovalRequest.PENDING)
        .select_related("node", "requested_by")
        .order_by("-decided_at")[:50]
    )

    return render(
        request,
        "dashboard/franchise_child_requests.html",
        {
            "active_menu": "franchise-child-requests",
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "is_reviewer": bool(parent_ids),
            "removal_pending": removal_pending,
            "removal_decided": removal_decided,
            "removal_next": "franchise-child-requests",
        },
    )


@login_required
@require_POST
@transaction.atomic
def franchise_child_action(request, application_id):
    """The direct parent approves/rejects a sub-franchise request. On approval
    the node is created PENDING_CONTRACT; the Platform Admin still activates it."""
    parent_ids = _reviewer_parent_ids(request.user)
    if not parent_ids:
        raise PermissionDenied()

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "reject"):
        messages.error(request, _("Invalid action."))
        return redirect("franchise-child-requests")

    application = get_object_or_404(
        FranchiseApplication.objects.filter(
            application_status__in=FranchiseApplicationStatus.OPEN,
            parent_franchise_id__in=parent_ids,
        ),
        id=application_id,
    )
    now = timezone.now()
    parent = application.parent_franchise

    if decision == "reject":
        board_note = (request.POST.get("board_note") or "").strip()[:BOARD_NOTE_MAX]
        if not board_note:
            conflict = _application_conflict(application)
            if conflict:
                board_note = _territory_taken_reason(conflict)
        application.application_status = FranchiseApplicationStatus.REJECTED
        application.rejected_by = request.user
        application.rejected_at = now
        application.board_note = board_note
        application.save(update_fields=[
            "application_status", "rejected_by", "rejected_at", "board_note", "updated_at",
        ])
        _audit_application(request, application, "franchise.rejected",
                           application_id=str(application.id),
                           requested_level=application.requested_level,
                           status=application.application_status, note=board_note,
                           parent_id=str(parent.id) if parent else None)
        _notify_decision(application, approved=False)
        messages.success(
            request,
            _("Rejected the sub-franchise request from %(email)s.") % {
                "email": application.applicant_user.email
            },
        )
        return redirect("franchise-child-requests")

    # Exclusivity (spec §11.1): one franchise per territory+level. Block
    # approving a duplicate — the parent should reject it instead.
    conflict = _application_conflict(application)
    if conflict:
        messages.error(
            request,
            _("Can't approve — %(reason)s Reject this request instead.")
            % {"reason": _territory_taken_reason(conflict)},
        )
        return redirect("franchise-child-requests")

    # Approve — parent must still be active (guarded by _reviewer_parent_ids).
    try:
        node = _create_node_from_application(application, parent=parent, reviewer=request.user, now=now)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("franchise-child-requests")

    _audit(request, node, "franchise.parent_approved",
           application_id=str(application.id), level=node.franchise_level,
           status=application.application_status, note=application.board_note,
           parent_id=str(parent.id))
    _notify_decision(application, approved=True)
    try:
        from accounts.utils.notifications import notify_franchise_awaiting_activation
        notify_franchise_awaiting_activation(node)
    except Exception:
        pass

    messages.success(
        request,
        _("Approved %(name)s. The Platform Admin will activate it after contract & payment.")
        % {"name": node.name},
    )
    return redirect("franchise-child-requests")


@login_required
@require_POST
@transaction.atomic
def franchise_activate(request, tenant_id):
    """Super Admin activates an approved franchise node (contract + payment done).

    This is the manual activation step (spec §2, §9.2): only here does the node
    reach ACTIVE and grant the holder full franchise rights. The Micro
    exclusivity + parent-active + territory checks run one more time, and the DB
    constraint is the final backstop against a race."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    node = get_object_or_404(
        Tenant.objects.filter(franchise_level__isnull=False),
        id=tenant_id,
    )
    if node.franchise_status == FranchiseUnitStatus.ACTIVE:
        messages.info(request, _("That franchise is already active."))
        return redirect("franchise-applications")

    now = timezone.now()
    # Fold contract signature + fee payment into activation for the MVP; the
    # fields stay separate so a future UI can split the steps.
    node.contract_status = ContractStatus.SIGNED
    node.franchise_fee_status = FranchiseFeeStatus.PAID
    node.franchise_status = FranchiseUnitStatus.ACTIVE
    node.activated_at = now
    if node.approved_by is None:
        node.approved_by = request.user

    try:
        node.clean()  # re-check exclusivity/parent now that status is ACTIVE
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("franchise-applications")

    try:
        node.save(update_fields=[
            "contract_status", "franchise_fee_status", "franchise_status",
            "activated_at", "approved_by", "updated_at",
        ])
    except IntegrityError:
        # Lost the exclusivity race — another Micro in this territory activated.
        messages.error(
            request,
            _("Could not activate: an active Micro-Franchise already exists in this territory."),
        )
        return redirect("franchise-applications")

    # Owning a franchise is ADDITIVE — the holder's role is left exactly as it
    # was. Activation used to overwrite it with the `franchise` role, which
    # stripped a Business User of every business-user capability: the company
    # switcher, plans, partnerships and the rest, so a BU with three companies
    # could act as only one of them ever again. The Franchise Management
    # section is driven by node ownership instead (accounts.utils.
    # franchise_access), and the UI simply relabels the holder as
    # "Franchise Partner" (accounts.role_i18n).
    owner = node.owner_user
    if owner is not None:
        owner_fields = []
        # Applicants who registered under a staff role (consultant / coordinator
        # / franchise) sit behind RequireApplicationApprovalMiddleware until
        # application_status == "approved". This holder was vetted through the
        # franchise application instead, so mark the staff application approved —
        # otherwise the gate bounces them onto the /apply/ region form.
        if (owner.application_status or "") != "approved":
            owner.application_status = "approved"
            owner.application_decided_by = request.user
            owner.application_decided_at = now
            owner_fields += ["application_status", "application_decided_by", "application_decided_at"]
        if owner_fields:
            owner.save(update_fields=owner_fields + ["updated_at"])

        # A Micro-Franchise owner "is also a consultant" (spec §9.1.2): record
        # them on their own node's roster as a MICRO_FRANCHISE_OWNER so they
        # appear in the consultant list and the certify / sell-plans capability
        # (gated by is_micro_franchise_owner) turns on. Non-Micro levels don't
        # get a self-assignment — they manage consultants, they aren't one.
        if node.franchise_level == FranchiseLevel.MICRO:
            ConsultantAssignment.objects.update_or_create(
                consultant_user=owner,
                franchise_node=node,
                status=ConsultantAssignmentStatus.ACTIVE,
                defaults=dict(
                    consultant_type=ConsultantType.MICRO_FRANCHISE_OWNER,
                    territory_country=node.territory_country,
                    territory_region=node.territory_region,
                    territory_city=node.territory_city,
                    assigned_by=request.user,
                    assigned_at=now,
                ),
            )

    _audit(request, node, "franchise.activated", level=node.franchise_level,
           status=node.franchise_status, contract_status=node.contract_status,
           payment_status=node.franchise_fee_status)
    try:
        from accounts.utils.notifications import notify_franchise_activated
        notify_franchise_activated(node)
    except Exception:
        pass

    messages.success(request, _("%(name)s is now active.") % {"name": node.name})
    return redirect("franchise-applications")


# ---------------------------------------------------------------------------
# Suspension (Rule 9) + consultant assignment (spec §8.3, §6, §17 #12)
# ---------------------------------------------------------------------------

def _sync_micro_owner_assignment(node, status):
    """Flip a Micro-Franchise owner's self-assignment (the MICRO_FRANCHISE_OWNER
    row created at activation) to match the node's status, so the node's
    consultant roster stays truthful across suspend / reactivate. No-op for
    non-Micro nodes, which never have a self-assignment."""
    if node.franchise_level != FranchiseLevel.MICRO or not node.owner_user_id:
        return
    ConsultantAssignment.objects.filter(
        consultant_user_id=node.owner_user_id,
        franchise_node=node,
        consultant_type=ConsultantType.MICRO_FRANCHISE_OWNER,
    ).exclude(status=ConsultantAssignmentStatus.TERMINATED).update(status=status)


@login_required
@require_POST
@transaction.atomic
def franchise_suspend(request, tenant_id):
    """Platform Admin suspends or reactivates a franchise node (Rule 9).

    A SUSPENDED node keeps its historical data but loses active rights — its
    owner can't add consultants or approve sub-franchises while suspended."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    action = (request.POST.get("action") or "").strip().lower()
    # Optional free-text reason recorded on the audit trail (spec §14).
    reason = (request.POST.get("reason") or "").strip()
    node = get_object_or_404(
        Tenant.objects.filter(franchise_level__isnull=False), id=tenant_id
    )
    now = timezone.now()

    if action == "suspend":
        if node.franchise_status != FranchiseUnitStatus.ACTIVE:
            messages.error(request, _("Only an active franchise can be suspended."))
            return redirect("franchise-applications")
        node.franchise_status = FranchiseUnitStatus.SUSPENDED
        node.suspended_at = now
        # Keep the generic `is_active` flag (the Franchises-list Status badge) in
        # step with the lifecycle status, so the list and the tree agree.
        node.is_active = False
        node.save(update_fields=["franchise_status", "suspended_at", "is_active", "updated_at"])
        # Keep a Micro owner's self-assignment in step so the suspended node's
        # roster doesn't list them as an active consultant (certify rights are
        # already off — is_micro_franchise_owner keys on the node's status).
        _sync_micro_owner_assignment(node, ConsultantAssignmentStatus.SUSPENDED)
        _audit(request, node, "franchise.suspended", level=node.franchise_level,
               status=node.franchise_status, reason=reason)
        messages.success(request, _("%(name)s has been suspended.") % {"name": node.name})
    elif action == "reactivate":
        if node.franchise_status != FranchiseUnitStatus.SUSPENDED:
            messages.error(request, _("Only a suspended franchise can be reactivated."))
            return redirect("franchise-applications")
        node.franchise_status = FranchiseUnitStatus.ACTIVE
        node.is_active = True
        try:
            node.clean()  # re-check exclusivity/parent on the way back to ACTIVE
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("franchise-applications")
        try:
            node.save(update_fields=["franchise_status", "is_active", "updated_at"])
        except IntegrityError:
            messages.error(
                request,
                _("Cannot reactivate: a Micro-Franchise already occupies this territory."),
            )
            return redirect("franchise-applications")
        _sync_micro_owner_assignment(node, ConsultantAssignmentStatus.ACTIVE)
        _audit(request, node, "franchise.reactivated", level=node.franchise_level,
               status=node.franchise_status, reason=reason)
        messages.success(request, _("%(name)s has been reactivated.") % {"name": node.name})
    else:
        messages.error(request, _("Invalid action."))
    return redirect("franchise-applications")


@login_required
@require_POST
def franchise_remove(request, tenant_id):
    """Platform Admin removes a franchise from its holder (spec §9.2 wind-down).

    Available for every level and every status — including a node that never
    reached ACTIVE — because the admin is the only authority that can take a
    territory back. Suspension pauses rights; removal ends them: the node and
    its sub-franchises are TERMINATED and soft-deleted, consultant rosters are
    closed, the applications behind them are CANCELLED, and each holder who is
    left with no franchise returns to Business User.

    `next` chooses where to land, so the same endpoint serves the Franchise
    Requests queue and the Franchises list.
    """
    if not request.user.is_superuser:
        raise PermissionDenied()

    reason = (request.POST.get("reason") or "").strip()
    redirect_to = "tenants" if request.POST.get("next") == "tenants" else "franchise-applications"

    # `Tenant.objects` hides soft-deleted rows, so an already-removed node 404s
    # instead of being wound down a second time.
    node = get_object_or_404(
        Tenant.objects.filter(franchise_level__isnull=False), id=tenant_id
    )
    name = node.name

    from accounts.utils.franchise_removal import remove_franchise

    result = remove_franchise(
        node, actor=request.user, reason=reason, ip_address=_client_ip(request),
    )

    descendants = result["descendant_count"]
    if descendants:
        messages.success(
            request,
            ngettext(
                "%(name)s was removed, along with the %(count)s sub-franchise beneath it.",
                "%(name)s was removed, along with the %(count)s sub-franchises beneath it.",
                descendants,
            ) % {"name": name, "count": descendants},
        )
    else:
        messages.success(
            request, _("%(name)s was removed.") % {"name": name},
        )
    return redirect(redirect_to)


# ---------------------------------------------------------------------------
# Giving up a franchise — the holder asks, the granting authority decides
# ---------------------------------------------------------------------------

def _removal_reviewer_node(node):
    """The node whose holder reviews a request to remove `node`.

    A sub-franchise is reviewed by its DIRECT parent — the holder who granted
    the territory (a Regional's exit is decided by the National above it). A
    Master has no parent, so it returns None and the request goes to the
    Platform Admin. A parent that is no longer active can't review anything, so
    that also falls back to the Admin.
    """
    parent = node.parent
    if parent is None or not parent.is_franchise_node:
        return None
    if parent.franchise_status != FranchiseUnitStatus.ACTIVE or not parent.owner_user_id:
        return None
    # Never route a request to the person making it — a holder who owns both the
    # node and its parent would otherwise approve their own exit.
    if parent.owner_user_id == node.owner_user_id:
        return None
    return parent


@login_required
@require_POST
@transaction.atomic
def franchise_removal_request(request, tenant_id):
    """A holder asks to give up one of their own franchises.

    Nothing is removed here: the request routes to the granting authority
    (direct parent holder, or the Platform Admin for a Master / an orphaned
    node) and only their approval winds the node down.
    """
    node = get_object_or_404(
        Tenant.objects.filter(franchise_level__isnull=False), id=tenant_id
    )
    if node.owner_user_id != request.user.id:
        messages.error(request, _("You can only give up a franchise you hold."))
        return redirect("franchise-request")

    if FranchiseRemovalRequest.objects.filter(
        node=node, status=FranchiseRemovalRequest.PENDING
    ).exists():
        messages.info(
            request,
            _("A removal request for %(name)s is already awaiting a decision.")
            % {"name": node.name},
        )
        return redirect("franchise-request")

    reviewer_node = _removal_reviewer_node(node)
    removal = FranchiseRemovalRequest.objects.create(
        node=node,
        requested_by=request.user,
        reviewer_franchise=reviewer_node,
        reason=(request.POST.get("reason") or "").strip()[:BOARD_NOTE_MAX],
    )
    _audit(request, node, "franchise.removal_requested",
           removal_request_id=str(removal.id), level=node.franchise_level,
           reviewer=(reviewer_node.name if reviewer_node else "platform_admin"))
    try:
        from accounts.utils.notifications import notify_franchise_removal_requested
        notify_franchise_removal_requested(removal)
    except Exception:
        pass

    if reviewer_node is not None:
        messages.success(
            request,
            _("Your request to give up %(name)s was sent to %(reviewer)s for approval.")
            % {"name": node.name, "reviewer": reviewer_node.name},
        )
    else:
        messages.success(
            request,
            _("Your request to give up %(name)s was sent to the Platform Admin for approval.")
            % {"name": node.name},
        )
    return redirect("franchise-request")


@login_required
@require_POST
@transaction.atomic
def franchise_removal_cancel(request, removal_id):
    """The holder withdraws their own pending removal request."""
    removal = get_object_or_404(
        FranchiseRemovalRequest.objects.filter(
            requested_by=request.user, status=FranchiseRemovalRequest.PENDING,
        ),
        id=removal_id,
    )
    removal.status = FranchiseRemovalRequest.CANCELLED
    removal.decided_by = request.user
    removal.decided_at = timezone.now()
    removal.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    _audit(request, removal.node, "franchise.removal_cancelled",
           removal_request_id=str(removal.id))
    messages.success(
        request,
        _("Your removal request for %(name)s was withdrawn.") % {"name": removal.node.name},
    )
    return redirect("franchise-request")


def _can_decide_removal(user, removal):
    """The Platform Admin decides Master (and orphaned) exits; a sub-franchise
    exit is decided by the holder of the reviewing parent node. The Admin can
    always step in, mirroring the override they have on applications."""
    if getattr(user, "is_superuser", False):
        return True
    reviewer_node = removal.reviewer_franchise
    return bool(
        reviewer_node is not None
        and reviewer_node.owner_user_id == user.id
        and reviewer_node.franchise_status == FranchiseUnitStatus.ACTIVE
    )


@login_required
@require_POST
@transaction.atomic
def franchise_removal_action(request, removal_id):
    """The reviewer approves or rejects a holder's request to give up a node.

    Approval runs the same wind-down as an admin removal: the node and its
    sub-franchises are TERMINATED and soft-deleted, consultant rosters close and
    the applications behind them are CANCELLED.
    """
    removal = get_object_or_404(
        FranchiseRemovalRequest.objects.select_related("node", "reviewer_franchise"),
        id=removal_id, status=FranchiseRemovalRequest.PENDING,
    )
    if not _can_decide_removal(request.user, removal):
        raise PermissionDenied()

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "reject"):
        messages.error(request, _("Invalid action."))
        return redirect(_removal_queue_redirect(request))

    removal.decision_note = (request.POST.get("decision_note") or "").strip()[:BOARD_NOTE_MAX]
    removal.decided_by = request.user
    removal.decided_at = timezone.now()

    if decision == "reject":
        removal.status = FranchiseRemovalRequest.REJECTED
        removal.save(update_fields=[
            "status", "decision_note", "decided_by", "decided_at", "updated_at",
        ])
        _audit(request, removal.node, "franchise.removal_rejected",
               removal_request_id=str(removal.id), note=removal.decision_note)
        try:
            from accounts.utils.notifications import notify_franchise_removal_decision
            notify_franchise_removal_decision(removal, approved=False)
        except Exception:
            pass
        messages.success(
            request,
            _("Declined the request to remove %(name)s.") % {"name": removal.node.name},
        )
        return redirect(_removal_queue_redirect(request))

    node = removal.node
    name = node.name
    removal.status = FranchiseRemovalRequest.APPROVED
    removal.save(update_fields=[
        "status", "decision_note", "decided_by", "decided_at", "updated_at",
    ])
    _audit(request, node, "franchise.removal_approved",
           removal_request_id=str(removal.id), note=removal.decision_note)
    try:
        from accounts.utils.notifications import notify_franchise_removal_decision
        notify_franchise_removal_decision(removal, approved=True)
    except Exception:
        pass

    from accounts.utils.franchise_removal import remove_franchise
    result = remove_franchise(
        node, actor=request.user, reason=removal.decision_note or removal.reason,
        ip_address=_client_ip(request),
    )
    descendants = result["descendant_count"]
    if descendants:
        messages.success(
            request,
            ngettext(
                "%(name)s was removed, along with the %(count)s sub-franchise beneath it.",
                "%(name)s was removed, along with the %(count)s sub-franchises beneath it.",
                descendants,
            ) % {"name": name, "count": descendants},
        )
    else:
        messages.success(request, _("%(name)s was removed.") % {"name": name})
    return redirect(_removal_queue_redirect(request))


def _removal_queue_redirect(request):
    """Land back on the queue the reviewer acted from."""
    target = (request.POST.get("next") or "").strip()
    if target in ("franchise-applications", "franchise-child-requests", "tenants"):
        return target
    return "franchise-applications" if request.user.is_superuser else "franchise-child-requests"


def pending_removal_requests_for(user):
    """Open removal requests `user` is the reviewer for — the Platform Admin's
    Master/orphaned exits, or a holder's own sub-franchise exits."""
    qs = FranchiseRemovalRequest.objects.filter(
        status=FranchiseRemovalRequest.PENDING
    ).select_related("node", "requested_by", "reviewer_franchise")
    if getattr(user, "is_superuser", False):
        return qs.filter(reviewer_franchise__isnull=True)
    parent_ids = _reviewer_parent_ids(user)
    if not parent_ids:
        return qs.none()
    return qs.filter(reviewer_franchise_id__in=parent_ids)


@login_required
def franchise_consultants(request):
    """A franchise holder's consultant roster + assign form (spec §8.3, §12)."""
    if not franchise_manager_required(request.user):
        raise PermissionDenied()

    owned = list(
        Tenant.objects.filter(owner_user=request.user, franchise_level__isnull=False)
        .order_by("name")
    )
    owned_ids = [n.id for n in owned]
    assignments_qs = (
        ConsultantAssignment.objects.filter(franchise_node_id__in=owned_ids)
        .exclude(status=ConsultantAssignmentStatus.TERMINATED)
        .select_related("consultant_user", "franchise_node", "assigned_by")
        .order_by("-created_at")
    )
    paginator, assignments = _paginate(request, assignments_qs, 10)
    # Only non-Micro levels can be assigned consultants (spec §9.6), so the
    # assign form must not offer a Micro node. The roster above still lists any
    # existing assignment under an owned Micro node so it stays removable.
    active_nodes = [
        n for n in owned
        if n.franchise_status == FranchiseUnitStatus.ACTIVE
        and n.franchise_level != FranchiseLevel.MICRO
    ]
    suspended_nodes = [n for n in owned if n.franchise_status == FranchiseUnitStatus.SUSPENDED]

    return render(
        request,
        "dashboard/franchise_consultants.html",
        {
            "active_menu": "franchise-consultants",
            "assignments": assignments,
            "page_obj": assignments,
            "total_count": paginator.count,
            "active_nodes": active_nodes,
            "has_suspended": bool(suspended_nodes),
        },
    )


@login_required
@require_POST
@transaction.atomic
def assign_consultant(request):
    """Assign a standard consultant under one of the holder's ACTIVE nodes.

    A SUSPENDED node cannot add consultants (Rule 9, §17 #12); a standard
    consultant carries no exclusivity (spec §6, Rule 8)."""
    if not is_franchise_holder(request.user):
        raise PermissionDenied()

    node = get_object_or_404(
        Tenant.objects.filter(owner_user=request.user, franchise_level__isnull=False),
        id=(request.POST.get("franchise_node_id") or "").strip(),
    )
    # A Micro-Franchise owner IS a consultant with local exclusivity — the
    # deepest level, with no one below to manage (spec §9.6: "Manage Standard
    # Consultants" = No for Micro). Only the levels above manage consultants.
    if node.franchise_level == FranchiseLevel.MICRO:
        messages.error(
            request,
            _("A Micro-Franchise can't manage consultants."),
        )
        return redirect("franchise-consultants")
    if node.franchise_status == FranchiseUnitStatus.SUSPENDED:
        messages.error(
            request,
            _("This franchise is suspended — you can't assign consultants while suspended."),
        )
        return redirect("franchise-consultants")
    if node.franchise_status != FranchiseUnitStatus.ACTIVE:
        messages.error(request, _("You can only assign consultants under an active franchise."))
        return redirect("franchise-consultants")

    email = (request.POST.get("consultant_email") or "").strip().lower()
    consultant = User.objects.filter(email__iexact=email, is_active=True).first()
    if not consultant:
        messages.error(request, _("No active user found with that email."))
        return redirect("franchise-consultants")
    if consultant.id == request.user.id:
        messages.error(request, _("You can't assign yourself as a consultant."))
        return redirect("franchise-consultants")

    assignment, created = ConsultantAssignment.objects.get_or_create(
        consultant_user=consultant,
        franchise_node=node,
        status=ConsultantAssignmentStatus.ACTIVE,
        defaults=dict(
            consultant_type=ConsultantType.STANDARD_CONSULTANT,
            territory_country=node.territory_country,
            territory_region=node.territory_region,
            territory_city=node.territory_city,
            assigned_by=request.user,
            assigned_at=timezone.now(),
        ),
    )
    if not created:
        messages.info(request, _("That consultant is already assigned to this franchise."))
    else:
        _audit(request, node, "consultant.assigned",
               consultant_id=str(consultant.id), status=assignment.status)
        messages.success(request, _("Assigned %(email)s as a consultant.") % {"email": consultant.email})
    return redirect("franchise-consultants")


@login_required
@require_POST
@transaction.atomic
def consultant_assignment_remove(request, assignment_id):
    """Revoke a consultant assignment the holder made."""
    if not is_franchise_holder(request.user):
        raise PermissionDenied()
    assignment = get_object_or_404(
        ConsultantAssignment.objects.filter(franchise_node__owner_user=request.user),
        id=assignment_id,
    )
    assignment.status = ConsultantAssignmentStatus.TERMINATED
    assignment.save(update_fields=["status", "updated_at"])
    _audit(request, assignment.franchise_node, "consultant.terminated",
           assignment_id=str(assignment.id), consultant_id=str(assignment.consultant_user_id),
           status=assignment.status)
    messages.success(request, _("Consultant removed."))
    return redirect("franchise-consultants")


# ---------------------------------------------------------------------------
# Franchise tree (spec §7, §12 'My Franchise Tree', §17 #9/#13)
# ---------------------------------------------------------------------------

@login_required
def franchise_tree(request):
    """Render the franchise tree scoped to what the viewer may see (spec §7).

    Platform Admin → the whole global forest (§7.4). A franchise holder → their
    own node(s) plus descendants only, so parallel branches are invisible
    (§7.1/§7.3, §17 #9). Others are denied."""
    if not franchise_manager_required(request.user):
        raise PermissionDenied()

    nodes = list(
        visible_nodes_qs(request.user)
        .select_related("parent", "owner_user")
        .order_by("name")
    )
    by_id = {n.id: n for n in nodes}
    children = {}
    roots = []
    for n in nodes:
        n.tree_children = []
    for n in nodes:
        if n.parent_id and n.parent_id in by_id:
            children.setdefault(n.parent_id, []).append(n)
        else:
            # Top of the *visible* forest — for a holder this is their own node
            # (its real parent is above their visibility ceiling).
            roots.append(n)
    _rank = {"MASTER": 1, "NATIONAL": 2, "REGIONAL": 3, "MICRO": 4}
    for n in nodes:
        n.tree_children = sorted(
            children.get(n.id, []), key=lambda c: (_rank.get(c.franchise_level, 9), c.name)
        )
    roots.sort(key=lambda c: (_rank.get(c.franchise_level, 9), c.name))

    return render(
        request,
        "dashboard/franchise_tree.html",
        {
            "active_menu": "franchise-tree",
            "roots": roots,
            "is_global": bool(request.user.is_superuser),
            "node_count": len(nodes),
        },
    )


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def _notify_decision(application, *, approved):
    try:
        from accounts.utils.notifications import notify_franchise_application_decision
        notify_franchise_application_decision(application, approved=approved)
    except Exception:
        pass


def pending_franchise_application_count(user):
    """Sidebar badge for the Platform Admin's queue — every open franchise
    request (MASTER plus sub-franchise requests routed to parents, which the
    Admin can also override-approve) plus every approved node awaiting
    activation."""
    if not user.is_authenticated or not user.is_superuser:
        return 0
    open_requests = FranchiseApplication.objects.filter(
        application_status__in=FranchiseApplicationStatus.OPEN,
    ).count()
    awaiting_activation = FranchiseApplication.objects.filter(
        application_status=FranchiseApplicationStatus.APPROVED,
        created_franchise__franchise_status__in=[
            FranchiseUnitStatus.PENDING_CONTRACT, FranchiseUnitStatus.PENDING_PAYMENT,
        ],
    ).count()
    # Master holders asking to give up their franchise are the Admin's call too.
    open_removals = FranchiseRemovalRequest.objects.filter(
        status=FranchiseRemovalRequest.PENDING, reviewer_franchise__isnull=True,
    ).count()
    return open_requests + awaiting_activation + open_removals


def pending_child_request_count(user):
    """Sidebar badge for a franchise holder — sub-franchise requests routed to
    their node(s) as the direct-parent operational reviewer (spec §4.2), plus
    requests from those sub-franchises to give their territory back."""
    if not user.is_authenticated or user.is_superuser:
        return 0
    parent_ids = _reviewer_parent_ids(user)
    if not parent_ids:
        return 0
    return FranchiseApplication.objects.filter(
        parent_franchise_id__in=parent_ids,
        application_status__in=FranchiseApplicationStatus.OPEN,
    ).count() + FranchiseRemovalRequest.objects.filter(
        reviewer_franchise_id__in=parent_ids,
        status=FranchiseRemovalRequest.PENDING,
    ).count()


# ---------------------------------------------------------------------------
# Add Sub-Franchise — a holder proposes a child under one of their nodes
# (spec §6.3 'Add Sub-Franchise')
# ---------------------------------------------------------------------------

@login_required
def franchise_add_subfranchise(request):
    """Form for an active franchise holder to propose a child franchise under one
    of their nodes (spec §6.3).

    The holder IS the direct parent, so their proposal counts as the parent's
    operational approval: the node is created in PENDING_CONTRACT immediately and
    the Platform Admin activates it after contract + payment — the same
    approved→activate tail as the outside-applicant flow, minus the review step
    the parent would otherwise perform."""
    if not is_franchise_holder(request.user):
        raise PermissionDenied()

    owned = list(
        Tenant.objects.filter(
            owner_user=request.user,
            franchise_level__isnull=False,
        ).order_by("name")
    )
    owned_active = [n for n in owned if n.franchise_status == FranchiseUnitStatus.ACTIVE]
    # Only nodes that can actually PARENT a sub-franchise belong in the form: a
    # Micro-Franchise is the deepest level and has no child levels (spec §8.2), so
    # it's excluded. A Micro-only owner therefore has no parent options at all.
    micro_rank = FranchiseLevel.RANK[FranchiseLevel.MICRO]
    active_nodes = [
        n for n in owned_active
        if FranchiseLevel.RANK.get(n.franchise_level, 0) < micro_rank
    ]
    # Distinguish the "no form" reasons so the page can explain itself:
    #  • suspended  — the holder's franchise(s) are suspended by the Admin, so
    #    they've lost creation rights until reactivated (spec §13 Rule 10).
    #  • micro_only — their only active franchise is a Micro (no child levels).
    suspended = (not owned_active) and any(
        n.franchise_status == FranchiseUnitStatus.SUSPENDED for n in owned
    )
    micro_only = bool(owned_active) and not active_nodes
    # Which sub-levels each parent node may spawn (anything strictly deeper), so
    # the form's level dropdown updates when the parent changes.
    node_options = []
    for n in active_nodes:
        p_rank = FranchiseLevel.RANK.get(n.franchise_level, 0)
        node_options.append({
            "id": str(n.id),
            "level_label": str(dict(FranchiseLevel.CHOICES).get(n.franchise_level, n.franchise_level)),
            "country": n.territory_country,
            "region": n.territory_region,
            "city": n.territory_city,
            "sub_levels": [
                {"value": lvl, "label": str(lbl)}
                for lvl, lbl in FranchiseLevel.CHOICES
                if FranchiseLevel.RANK.get(lvl, 0) > p_rank
            ],
        })

    return render(request, "dashboard/franchise_add_subfranchise.html", {
        "active_menu": "franchise-add-subfranchise",
        "active_nodes": active_nodes,
        "node_options_json": json.dumps(node_options),
        "has_active_node": bool(active_nodes),
        "micro_only": micro_only,
        "suspended": suspended,
        "contract_choices": ContractStatus.CHOICES,
        "fee_choices": FranchiseFeeStatus.CHOICES,
        # Country -> subdivisions for the State/Region dropdown (falls back to
        # free text for countries not in the map).
        "country_states": COUNTRY_STATES,
        # Repopulate the form after a validation-error redirect (popped so it
        # only pre-fills once).
        "form_data": request.session.pop("subfranchise_form", None) or {},
    })


@login_required
@require_POST
@transaction.atomic
def franchise_subfranchise_submit(request):
    """Process a holder's Add Sub-Franchise proposal (see
    `franchise_add_subfranchise`)."""
    if not is_franchise_holder(request.user):
        raise PermissionDenied()

    # Preserve the proposal so a validation-error redirect repopulates the form
    # rather than wiping every field (cleared on success below).
    request.session["subfranchise_form"] = {
        k: (request.POST.get(k) or "") for k in (
            "parent_node_id", "requested_level", "requested_region",
            "requested_city", "requested_local_area", "legal_name",
            "contact_person", "owner_email", "contact_phone",
            "contract_status", "fee_status", "application_note",
        )
    }

    parent = get_object_or_404(
        Tenant.objects.filter(owner_user=request.user, franchise_level__isnull=False),
        id=(request.POST.get("parent_node_id") or "").strip(),
    )
    if parent.franchise_status != FranchiseUnitStatus.ACTIVE:
        messages.error(request, _("You can only add sub-franchises under an active franchise."))
        return redirect("franchise-add-subfranchise")

    level = (request.POST.get("requested_level") or "").strip().upper()
    if level not in dict(FranchiseLevel.CHOICES) or level == FranchiseLevel.MASTER:
        messages.error(request, _("Please choose a valid sub-franchise level."))
        return redirect("franchise-add-subfranchise")
    if FranchiseLevel.RANK.get(level, 0) <= FranchiseLevel.RANK.get(parent.franchise_level, 0):
        messages.error(request, _("A sub-franchise must sit below the parent franchise's level."))
        return redirect("franchise-add-subfranchise")

    # A sub-franchise territory is contained in the parent's — inherit the
    # parent's country and reduce the rest to what the chosen level occupies.
    country = parent.territory_country or (request.POST.get("requested_country") or "").strip().upper()[:2]
    region = (request.POST.get("requested_region") or "").strip()[:120]
    city = (request.POST.get("requested_city") or "").strip()[:120]
    local_area = (request.POST.get("requested_local_area") or "").strip()[:120]
    country, region, city, local_area = canonical_territory(level, country, region, city, local_area)

    if level in (FranchiseLevel.REGIONAL, FranchiseLevel.MICRO) and not region:
        messages.error(request, _("Please enter the region / state for this sub-franchise."))
        return redirect("franchise-add-subfranchise")
    if level == FranchiseLevel.MICRO and not city:
        messages.error(request, _("Please enter the city for a Micro-Franchise."))
        return redirect("franchise-add-subfranchise")

    # The region must be a real subdivision of the (inherited) country when one
    # is required — free-text only for countries without a known subdivision list.
    if region:
        canon = canonical_region(country, region)
        if canon is None:
            messages.error(request, _("Please choose a valid state / region for the selected country."))
            return redirect("franchise-add-subfranchise")
        region = canon

    # The territory must fall inside the parent's (spec Rule 3). Pre-check here so
    # a bad request is rejected before any row is written.
    probe = Tenant(
        territory_country=country, territory_region=region,
        territory_city=city, territory_local_area=local_area,
    )
    if not probe.is_territory_within(parent):
        messages.error(request, _("The sub-franchise territory must be inside the parent franchise's territory."))
        return redirect("franchise-add-subfranchise")

    # Prospective owner — must already have an active account. They become the
    # holder when the Platform Admin activates the node, exactly like an outside
    # applicant. Consistent with how consultants are added (lookup by email).
    email = (request.POST.get("owner_email") or "").strip().lower()
    if not email:
        messages.error(request, _("Please enter the email of the sub-franchise owner."))
        return redirect("franchise-add-subfranchise")
    owner = User.objects.filter(email__iexact=email, is_active=True, is_deleted=False).first()
    if not owner:
        messages.error(request, _("No active user found with that email. The sub-franchise owner must already have an account."))
        return redirect("franchise-add-subfranchise")

    # A user may hold several franchises, but never two whose territories
    # overlap — they'd be their own franchisee. The model's clean() is the
    # authoritative backstop (and rolls the row back); checking here gives the
    # proposing holder a clear message up front.
    overlap = Tenant(
        parent=parent, owner_user=owner, franchise_level=level,
        territory_country=country, territory_region=region,
        territory_city=city, territory_local_area=local_area,
    ).conflicting_franchise_owned()
    if overlap is not None:
        messages.error(
            request,
            _("%(email)s already holds %(name)s, whose territory overlaps this one. "
              "A holder cannot also hold a franchise inside their own territory.")
            % {"email": owner.email, "name": overlap.name},
        )
        return redirect("franchise-add-subfranchise")

    # One franchise per territory+level (spec §11.1).
    conflict = territory_conflict(level, country, region, city, local_area)
    if conflict is not None:
        messages.error(request, _territory_taken_reason(conflict))
        return redirect("franchise-add-subfranchise")

    # Business + contact details captured on the form (spec §8.1).
    legal_name = (request.POST.get("legal_name") or "").strip()[:255]
    contact_person = (request.POST.get("contact_person") or "").strip()[:255]
    contact_phone = (request.POST.get("contact_phone") or "").strip()[:40]
    if not legal_name:
        messages.error(request, _("Please enter the legal / company name for the sub-franchise."))
        return redirect("franchise-add-subfranchise")
    if not contact_person:
        messages.error(request, _("Please enter the contact person for the sub-franchise."))
        return redirect("franchise-add-subfranchise")

    # Initial contract / payment status the holder recorded (spec §8.1). The node
    # is still created PENDING_CONTRACT — only the Platform Admin's activation
    # flips it to ACTIVE (§5) — but these let the holder note that a contract is
    # already signed or the fee already paid.
    contract_status = (request.POST.get("contract_status") or "").strip().upper()
    if contract_status not in dict(ContractStatus.CHOICES):
        contract_status = ContractStatus.PENDING
    fee_status = (request.POST.get("fee_status") or "").strip().upper()
    if fee_status not in dict(FranchiseFeeStatus.CHOICES):
        fee_status = FranchiseFeeStatus.UNPAID

    note = (request.POST.get("application_note") or "").strip()
    now = timezone.now()
    try:
        # Nested savepoint so a late tree-invariant failure in
        # _create_node_from_application rolls back the application row too.
        with transaction.atomic():
            application = FranchiseApplication.objects.create(
                applicant_user=owner,
                requested_level=level,
                requested_country=country,
                requested_region=region,
                requested_city=city,
                requested_local_area=local_area,
                parent_franchise=parent,
                legal_name=legal_name,
                contact_person=contact_person,
                contact_phone=contact_phone,
                application_note=note,
                application_status=FranchiseApplicationStatus.SUBMITTED,
            )
            node = _create_node_from_application(
                application, parent=parent, reviewer=request.user, now=now,
                node_name=legal_name, contract_status=contract_status,
                fee_status=fee_status,
            )
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("franchise-add-subfranchise")

    _audit(request, node, "franchise.parent_proposed",
           application_id=str(application.id), level=node.franchise_level,
           parent_id=str(parent.id), owner_id=str(owner.id))
    try:
        from accounts.utils.notifications import notify_franchise_awaiting_activation
        notify_franchise_awaiting_activation(node)
    except Exception:
        pass
    _notify_decision(application, approved=True)

    # Proposed cleanly — drop the preserved values so the form comes back empty.
    request.session.pop("subfranchise_form", None)

    messages.success(
        request,
        _("Proposed %(name)s under %(parent)s. The Platform Admin will activate it after contract & payment.")
        % {"name": node.name, "parent": parent.name},
    )
    return redirect("franchise-add-subfranchise")


# ---------------------------------------------------------------------------
# Subtree business data — certified companies, plan sales, reports
# (spec §6.3). All three scope through the consultants operating under the
# viewer's visible franchise subtree.
# ---------------------------------------------------------------------------

@login_required
def franchise_certified_companies(request):
    """Companies certified by the consultants operating within the viewer's
    franchise subtree (spec §6.3 'Certified Companies')."""
    if not franchise_manager_required(request.user):
        raise PermissionDenied()

    consultant_ids = subtree_consultant_ids(request.user)
    companies = (
        Company.objects.filter(
            Q(certified_by_id__in=consultant_ids) | Q(consultant_id__in=consultant_ids),
            certification_status="certified",
        )
        .select_related("certified_by", "consultant")
        .distinct()
        .order_by("name")
    )
    q = (request.GET.get("q") or "").strip()
    if q:
        for token in q.split():
            companies = companies.filter(
                Q(name__icontains=token)
                | Q(country__icontains=token)
                | Q(city__icontains=token)
            )

    paginator, page_obj = _paginate(request, companies, 10)
    return render(request, "dashboard/franchise_certified_companies.html", {
        "active_menu": "franchise-certified-companies",
        "companies": page_obj,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "search_query": q,
        "no_consultants": not consultant_ids,
    })


@login_required
def franchise_sales(request):
    """Plan subscriptions sold within the viewer's franchise subtree — plans
    bought by companies certified by the subtree's consultants (spec §6.3
    'Sales / Plans')."""
    if not franchise_manager_required(request.user):
        raise PermissionDenied()

    from billing.models import Subscription

    consultant_ids = subtree_consultant_ids(request.user)
    subs = (
        Subscription.objects.filter(
            Q(company__certified_by_id__in=consultant_ids)
            | Q(company__consultant_id__in=consultant_ids),
        )
        .select_related("plan", "company", "user")
        .order_by("-created_at")
    )
    status = (request.GET.get("status") or "").strip()
    if status:
        subs = subs.filter(status=status)

    paginator, page_obj = _paginate(request, subs, 10)
    return render(request, "dashboard/franchise_sales.html", {
        "active_menu": "franchise-sales",
        "sales": page_obj,
        "page_obj": page_obj,
        "total_count": paginator.count,
        "status_filter": status,
        "status_choices": Subscription.STATUS_CHOICES,
        "no_consultants": not consultant_ids,
    })


@login_required
def franchise_reports(request):
    """Franchise subtree summary report with simple filters (spec §6.3
    'Reports'): period, territory, franchise level, consultant, and status.

    Everything is scoped to the viewer's visible subtree; the filters narrow the
    franchise nodes, and the business KPIs (consultants, certified companies,
    plan sales) resolve through the consultants operating under the filtered
    nodes."""
    if not franchise_manager_required(request.user):
        raise PermissionDenied()

    node_ids = visible_node_ids(request.user)
    nodes = Tenant.objects.filter(id__in=node_ids, franchise_level__isnull=False)

    level = (request.GET.get("level") or "").strip().upper()
    status = (request.GET.get("status") or "").strip().upper()
    country = (request.GET.get("country") or "").strip().upper()
    region = (request.GET.get("region") or "").strip()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()
    consultant_id = (request.GET.get("consultant") or "").strip()

    if level in dict(FranchiseLevel.CHOICES):
        nodes = nodes.filter(franchise_level=level)
    if status in dict(FranchiseUnitStatus.CHOICES):
        nodes = nodes.filter(franchise_status=status)
    if country:
        nodes = nodes.filter(territory_country=country)
    if region:
        nodes = nodes.filter(territory_region__icontains=region)
    # "Period" filters on when the franchise node was created.
    if date_from:
        nodes = nodes.filter(created_at__date__gte=date_from)
    if date_to:
        nodes = nodes.filter(created_at__date__lte=date_to)

    nodes = list(nodes.select_related("owner_user").order_by("franchise_level", "name"))
    filtered_ids = [n.id for n in nodes]

    assignments = ConsultantAssignment.objects.filter(
        franchise_node_id__in=filtered_ids,
        status=ConsultantAssignmentStatus.ACTIVE,
    )
    if consultant_id:
        assignments = assignments.filter(consultant_user_id=consultant_id)
    consultant_ids = set(assignments.values_list("consultant_user_id", flat=True))

    certified_count = (
        Company.objects.filter(
            Q(certified_by_id__in=consultant_ids) | Q(consultant_id__in=consultant_ids),
            certification_status="certified",
        )
        .distinct()
        .count()
    )

    from billing.models import Subscription

    sales_qs = Subscription.objects.filter(
        Q(company__certified_by_id__in=consultant_ids)
        | Q(company__consultant_id__in=consultant_ids),
    )
    if date_from:
        sales_qs = sales_qs.filter(created_at__date__gte=date_from)
    if date_to:
        sales_qs = sales_qs.filter(created_at__date__lte=date_to)

    kpis = {
        "nodes": len(nodes),
        "active": sum(1 for n in nodes if n.franchise_status == FranchiseUnitStatus.ACTIVE),
        "suspended": sum(1 for n in nodes if n.franchise_status == FranchiseUnitStatus.SUSPENDED),
        "consultants": len(consultant_ids),
        "certified_companies": certified_count,
        "sales": sales_qs.count(),
    }
    by_level = []
    for lvl, lbl in FranchiseLevel.CHOICES:
        c = sum(1 for n in nodes if n.franchise_level == lvl)
        if c:
            by_level.append({"label": str(lbl), "count": c})

    # Consultant dropdown lists everyone in the (unfiltered) subtree.
    consultants = User.objects.filter(
        id__in=subtree_consultant_ids(request.user, node_ids)
    ).order_by("first_name", "last_name")

    # Paginate the "franchises in scope" table (the KPIs above stay full-set totals).
    paginator, nodes_page = _paginate(request, nodes, 10)
    from django.utils.http import urlencode
    filter_qs = urlencode({k: v for k, v in request.GET.items() if k != "page" and v})

    return render(request, "dashboard/franchise_reports.html", {
        "active_menu": "franchise-reports",
        "nodes": nodes_page,
        "page_obj": nodes_page,
        "filter_qs": filter_qs,
        "kpis": kpis,
        "by_level": by_level,
        "level_choices": FranchiseLevel.CHOICES,
        "status_choices": FranchiseUnitStatus.CHOICES,
        "consultants": consultants,
        "country_choices": CountryChoices.CHOICES,
        "filters": {
            "level": level, "status": status, "country": country, "region": region,
            "from": date_from, "to": date_to, "consultant": consultant_id,
        },
    })
