"""Consultant-facing certification workflow.

When a Business User submits a new company via the "Request Certification"
button, the company is stored with `certification_status='pending'` and
`is_active=False` (so it stays out of the public directory), and the request
is routed to a consultant in the same locality. The consultant reviews and
either approves (company goes live, BU is notified) or declines (company stays
inactive, status set to 'rejected').

Mirrors the structure of `partnership.py` so the two flows feel consistent.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from accounts.models import AuditLog, Company
from accounts.utils.ip import get_client_ip
from accounts.utils.permissions import can_certify_companies, is_suspended_micro_owner


#: Rows per tab on the Certifications page.
CERT_PAGE_SIZE = 10


def _cert_page(request, qs, param):
    """Paginate one Certifications tab.

    Each tab carries its own ?page param so paging one doesn't reset the
    others. `get_page` is deliberate: it clamps junk / out-of-range values to a
    valid page instead of raising, which matters because these numbers come
    straight off the query string.
    """
    from django.core.paginator import Paginator

    return Paginator(qs, CERT_PAGE_SIZE).get_page(request.GET.get(param))


def _suspended_page(request, feature):
    """Render the 'your franchise is suspended' page for a suspended Micro owner
    who tries to reach a certifier-only tab (spec §13 Rule 10)."""
    return render(request, "dashboard/franchise_suspended.html", {"feature": feature})


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _require_consultant(user):
    """Only certifiers may use these endpoints: superusers, Standard Consultants,
    and Micro-Franchise owners (a consultant-level franchise — spec §9.1.2, §11).
    Mirrors the partnership module's role gate so the failure mode is consistent:
    a 403 page rather than a silent 404."""
    if not can_certify_companies(user):
        raise PermissionDenied("Only consultants can manage certifications.")


def _user_role_code(user):
    if user.is_superuser:
        return "superuser"
    return (user.role.code or "").lower() if user.role else ""


@login_required
def certification_list(request):
    """Renders the Certifications page in one of two modes:

      • Consultant / superuser — review queue with Approve/Decline + the
        consultant's own certified+rejected history.
      • Business user — read-only view of their own outstanding requests
        and their decision history. No Approve/Decline buttons.

    The same template handles both; `view_mode` toggles which sections
    render.
    """
    role_code = _user_role_code(request.user)

    if role_code == "business_user":
        # A BU sees the certification status of just their ACTIVE company — the
        # one selected in the company switcher (session), matching every other
        # per-company page. A BU who owns several companies switches company to
        # see another's certification, rather than seeing them all mixed here.
        from billing.utils import resolve_active_company
        active_company = resolve_active_company(request.user)
        owned = (
            Company.objects.filter(owner_user=request.user, id=active_company.id)
            if active_company
            else Company.objects.none()
        )

        # Same annotation as the reviewer queue below, so the BU's own card
        # shows the date of the request they actually just sent.
        pending = (
            owned.filter(certification_status="pending")
            .select_related("consultant", "certified_by")
            .annotate(
                submitted_at=Coalesce("certification_requested_at", "created_at")
            )
            .order_by("-submitted_at")
        )
        certified = owned.filter(
            certification_status="certified"
        ).select_related("certified_by").order_by("-certified_at")
        rejected = owned.filter(
            certification_status="rejected"
        ).select_related("consultant").order_by("-updated_at")

        return render(
            request,
            "dashboard/certifications.html",
            {
                "active_menu": "certifications",
                "view_mode": "bu",
                "pending": pending,
                "certified": certified,
                "rejected": rejected,
            },
        )

    # A Micro-Franchise owner whose franchise is suspended keeps the tab visible
    # but can't act — show a clear "suspended" message instead of a 403.
    if is_suspended_micro_owner(request.user):
        return _suspended_page(request, _("Certifications"))

    # Default: reviewer view. Consultants, active Micro owners, superusers.
    _require_consultant(request.user)

    # Broadcast model: every consultant sees unclaimed pending requests plus
    # any they've personally claimed. First consultant to approve wins.
    pending_qs = Company.objects.filter(certification_status="pending")
    if not request.user.is_superuser:
        pending_qs = pending_qs.filter(
            Q(consultant__isnull=True) | Q(consultant=request.user)
        # A consultant can't certify their own company, so never show one they
        # own in their pending queue.
        ).exclude(owner_user=request.user)
    # Newest REQUEST first, not newest company: a resubmission is a fresh
    # request and belongs at the top of the queue, however old the company row
    # is. Coalesce covers rows that predate certification_requested_at and were
    # not pending when the backfill ran (0062), so they still sort sensibly
    # instead of collapsing to the bottom on a NULL.
    pending = (
        pending_qs.select_related("tenant", "owner_user")
        .annotate(
            submitted_at=Coalesce("certification_requested_at", "created_at")
        )
        .order_by("-submitted_at")
    )

    # Superusers oversee everything, so they see every certified / rejected
    # company (mirroring the pending tab). Consultants only see the ones they
    # personally certified / declined. This also fixes the case where a super
    # admin declines a request (no consultant FK is set on a superuser decline)
    # and it would otherwise never appear in the Declined tab.
    certified_qs = Company.objects.filter(certification_status="certified")
    if not request.user.is_superuser:
        certified_qs = certified_qs.filter(certified_by=request.user)
    certified = certified_qs.select_related("tenant", "owner_user").order_by("-certified_at")

    rejected_qs = Company.objects.filter(certification_status="rejected")
    if not request.user.is_superuser:
        rejected_qs = rejected_qs.filter(consultant=request.user)
    rejected = rejected_qs.select_related("tenant", "owner_user").order_by("-updated_at")

    # The tab badges must show the TOTAL, not the current page's length, so the
    # counts are taken before paginating.
    pending_total = pending.count()
    certified_total = certified.count()
    rejected_total = rejected.count()

    # `tab` survives a page click so the user lands back on the list they were
    # paging, rather than being bounced to Pending.
    active_tab = request.GET.get("tab") or "pending"
    if active_tab not in ("pending", "certified", "rejected", "certificates"):
        active_tab = "pending"

    return render(
        request,
        "dashboard/certifications.html",
        {
            "active_menu": "certifications",
            "view_mode": "consultant",
            "pending": _cert_page(request, pending, "pp"),
            "certified": _cert_page(request, certified, "pc"),
            "rejected": _cert_page(request, rejected, "pr"),
            # Same rows as `certified`, paged independently — the Certificates
            # tab is a separate list the user scrolls on its own.
            "certificates": _cert_page(request, certified, "pcert"),
            "pending_total": pending_total,
            "certified_total": certified_total,
            "rejected_total": rejected_total,
            "active_tab": active_tab,
        },
    )


@login_required
@require_POST
@transaction.atomic
def certification_action(request, company_id):
    """Approve or decline a pending certification request.

    Approve  → certification_status='certified', is_active=True, certified_by
              and certified_at populated. The owner_user sees a banner next
              time they hit a dashboard page.
    Decline  → certification_status='rejected'. is_active stays False so the
              company remains out of the public directory. The owner_user
              can refile via the same form.
    """
    # A suspended Micro owner can't certify — friendly message, not a 403.
    if is_suspended_micro_owner(request.user):
        msg = _("Your franchise is suspended, so you can't certify companies. Please contact the Platform Admin.")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect("certifications")
    _require_consultant(request.user)

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "decline"):
        msg = _("Invalid action.")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("certifications")

    # Look up against all_objects so deactivated pending rows are still found.
    # A consultant can act on requests they've claimed AND on any unclaimed
    # pending request (broadcast model). The transaction + status filter make
    # this race-safe: if two consultants approve at once, only the first one
    # finds the row in pending state; the second gets a 404.
    scope = Company.objects.filter(certification_status="pending")
    if not request.user.is_superuser:
        scope = scope.filter(
            Q(consultant__isnull=True) | Q(consultant=request.user)
        )

    company = get_object_or_404(scope, id=company_id)

    # A consultant must never certify (or decline) a company they own — you
    # can't vet your own submission. Consultant-created companies are
    # auto-certified at creation so this normally can't arise, but guard the
    # action server-side too. Superusers are exempt (platform oversight).
    if not request.user.is_superuser and company.owner_user_id == request.user.id:
        msg = _("You can't certify your own company.")
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect("certifications")

    if decision == "approve":
        company.certification_status = "certified"
        company.is_active = True
        company.certified_by = request.user
        company.certified_at = timezone.now()
        # Claim ownership for the approving consultant (drives commission
        # attribution and the My Companies / consultant_companies views).
        update_fields = [
            "certification_status", "is_active", "certified_by", "certified_at"
        ]
        if not company.consultant_id and not request.user.is_superuser:
            company.consultant = request.user
            update_fields.append("consultant")
        company.save(update_fields=update_fields)
        action = "company.certified"
        success_msg = _("Approved certification for %(company)s.") % {"company": company.name}
    else:
        company.certification_status = "rejected"
        company.is_active = False
        update_fields = ["certification_status", "is_active"]
        # Claim the request for the declining consultant so it appears in their
        # "Declined" tab (which filters by consultant=request.user). Without
        # this the declined company keeps consultant=NULL and never shows up.
        # Mirrors the approve branch.
        if not company.consultant_id and not request.user.is_superuser:
            company.consultant = request.user
            update_fields.append("consultant")
        company.save(update_fields=update_fields)
        action = "company.certification_declined"
        success_msg = _("Declined certification for %(company)s.") % {"company": company.name}

    try:
        AuditLog.objects.create(
            tenant=company.tenant,
            actor=request.user,
            action=action,
            entity_type="Company",
            entity_id=company.id,
            metadata={
                "company_name": company.name,
                "decision": decision,
            },
            ip_address=get_client_ip(request),
        )
    except Exception:
        # Audit failures never block the certification decision.
        pass

    try:
        from accounts.utils.notifications import notify_certification_decision
        notify_certification_decision(
            company,
            decided_by=request.user,
            approved=(decision == "approve"),
        )
    except Exception:
        pass

    # Commission is owed to the consultant who CERTIFIED the company. If the
    # company owner (business user) already has an approved paid plan, certifying
    # their company now makes this consultant eligible — (re)try commission
    # creation for the owner's paid subscriptions. Idempotent, so safe; also
    # fires the consultant + super-admin commission notifications.
    if decision == "approve" and company.owner_user_id:
        try:
            from billing.views import backfill_consultant_commissions_for_user
            backfill_consultant_commissions_for_user(company.owner_user)
        except Exception:
            pass

    if _is_ajax(request):
        return JsonResponse({
            "ok": True,
            "decision": decision,
            "status": company.certification_status,
            "message": success_msg,
        })

    messages.success(request, success_msg)
    return redirect(reverse("certifications"))


@login_required
def certificate_view(request, company_id):
    """Printable certificate for a certified company.

    Reachable from the Certificates tab and from the company owner's own
    Certifications page. Visible to the superuser, the consultant who issued
    it, and the company's owner — a certificate is the owner's document, so
    locking it to the issuer alone would be wrong.

    A company that isn't certified has no certificate to show; that's a 404
    rather than an empty page, so the URL can't be used to probe which
    companies exist in a pending state.
    """
    company = get_object_or_404(
        Company.objects.select_related("certified_by", "owner_user", "tenant"),
        id=company_id,
        certification_status="certified",
    )

    user = request.user
    allowed = (
        user.is_superuser
        or company.certified_by_id == user.id
        or company.owner_user_id == user.id
    )
    if not allowed:
        raise PermissionDenied

    return render(
        request,
        "dashboard/certificate.html",
        {"company": company, "active_menu": "certifications"},
    )


def pending_certification_count(user):
    """Used by the navbar context processor to render the badge next to the
    Certifications link. Returns 0 for non-consultants so we don't render a
    badge for users who shouldn't see the page in the first place."""
    if not user.is_authenticated:
        return 0
    # Consultants, Micro-Franchise owners, and superusers all have a queue.
    if not can_certify_companies(user):
        return 0
    qs = Company.objects.filter(certification_status="pending")
    if not user.is_superuser:
        qs = qs.filter(Q(consultant__isnull=True) | Q(consultant=user))
    return qs.count()
