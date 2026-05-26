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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AuditLog, Company
from accounts.utils.ip import get_client_ip


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _require_consultant(user):
    """Only users with the `consultant` role (or superusers) may use these
    endpoints. Mirrors the partnership module's role gate so the failure mode
    is consistent: a 403 page rather than a silent 404."""
    if user.is_superuser:
        return
    role_code = (user.role.code or "").lower() if user.role else ""
    if role_code != "consultant":
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
        # BUs see the status of every company they own (typically just one
        # — their primary — but the model allows extras). All three states
        # are surfaced as separate sections so the user can scan history
        # without filtering tabs.
        owned = Company.all_objects.filter(owner_user=request.user)

        pending = owned.filter(
            certification_status="pending"
        ).select_related("consultant", "certified_by").order_by("-created_at")
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

    # Default: reviewer view. Consultants and superusers only.
    _require_consultant(request.user)

    # Broadcast model: every consultant sees unclaimed pending requests plus
    # any they've personally claimed. First consultant to approve wins.
    pending_qs = Company.all_objects.filter(certification_status="pending")
    if not request.user.is_superuser:
        pending_qs = pending_qs.filter(
            Q(consultant__isnull=True) | Q(consultant=request.user)
        )
    pending = pending_qs.select_related("tenant", "owner_user").order_by("-created_at")

    certified_qs = Company.all_objects.filter(
        certification_status="certified",
        certified_by=request.user,
    )
    certified = certified_qs.select_related("tenant", "owner_user").order_by("-certified_at")

    rejected_qs = Company.all_objects.filter(
        certification_status="rejected",
        consultant=request.user,
    )
    rejected = rejected_qs.select_related("tenant", "owner_user").order_by("-updated_at")

    return render(
        request,
        "dashboard/certifications.html",
        {
            "active_menu": "certifications",
            "view_mode": "consultant",
            "pending": pending,
            "certified": certified,
            "rejected": rejected,
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
    _require_consultant(request.user)

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "decline"):
        msg = "Invalid action."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("certifications")

    # Look up against all_objects so deactivated pending rows are still found.
    # A consultant can act on requests they've claimed AND on any unclaimed
    # pending request (broadcast model). The transaction + status filter make
    # this race-safe: if two consultants approve at once, only the first one
    # finds the row in pending state; the second gets a 404.
    scope = Company.all_objects.filter(certification_status="pending")
    if not request.user.is_superuser:
        scope = scope.filter(
            Q(consultant__isnull=True) | Q(consultant=request.user)
        )

    company = get_object_or_404(scope, id=company_id)

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
        success_msg = f"Approved certification for {company.name}."
    else:
        company.certification_status = "rejected"
        company.is_active = False
        company.save(update_fields=["certification_status", "is_active"])
        action = "company.certification_declined"
        success_msg = f"Declined certification for {company.name}."

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

    if _is_ajax(request):
        return JsonResponse({
            "ok": True,
            "decision": decision,
            "status": company.certification_status,
            "message": success_msg,
        })

    messages.success(request, success_msg)
    return redirect(reverse("certifications"))


def pending_certification_count(user):
    """Used by the navbar context processor to render the badge next to the
    Certifications link. Returns 0 for non-consultants so we don't render a
    badge for users who shouldn't see the page in the first place."""
    if not user.is_authenticated:
        return 0
    role_code = (user.role.code or "").lower() if user.role else ""
    if not user.is_superuser and role_code != "consultant":
        return 0
    qs = Company.all_objects.filter(certification_status="pending")
    if not user.is_superuser:
        qs = qs.filter(Q(consultant__isnull=True) | Q(consultant=user))
    return qs.count()
