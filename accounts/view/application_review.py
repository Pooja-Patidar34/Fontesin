"""Super-admin review of coordinator / franchise account applications.

A user registers as coordinator/franchise → completes Veriff → fills the apply
form (application_status="submitted"). That submission notifies every super
admin, who reviews it here and Approves or Declines. Until approved the account
is held on the "application under review" page by
RequireApplicationApprovalMiddleware. On approve they get full access; on
decline they stay blocked with the reason. The applicant is notified either way.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User, DueDiligence


# Roles that go through super-admin application approval (see
# RequireApplicationApprovalMiddleware.GATED_ROLE_CODES). Role codes are stored
# case-insensitively in the DB (e.g. "COORDINATOR"), so match with iexact.
GATED_ROLE_CODES = ("coordinator", "franchise")
GATED_ROLE_Q = Q(role__code__iexact="coordinator") | Q(role__code__iexact="franchise")


def _role_code(user):
    return (user.role.code or "").lower() if user.role else ""


@login_required
def application_pending(request):
    """The applicant's 'under review' / 'declined' screen while a coordinator/
    franchise account waits on (or was refused) super-admin approval."""
    user = request.user
    status = (user.application_status or "")

    # Approved users have nothing to wait for — send them on.
    if status == "approved":
        return redirect("dashboard")

    # Not a gated role, or hasn't applied yet → they don't belong here.
    if _role_code(user) not in GATED_ROLE_CODES:
        return redirect("dashboard")
    if status not in ("submitted", "declined"):
        return redirect("apply")

    role_label = (user.role.name or user.role.code or "").replace("_", " ").title() if user.role else ""
    return render(
        request,
        "auth/application_pending.html",
        {
            "status": status,
            "role_label": role_label,
            "decline_reason": (user.application_decline_reason or "").strip(),
        },
    )


def _serialize_due_diligence(user):
    dd = DueDiligence.objects.filter(user=user).first()
    if not dd:
        return None
    return {
        "criminal_offence": dd.criminal_offence,
        "criminal_offence_details": dd.criminal_offence_details,
        "regulatory_sanctions": dd.regulatory_sanctions,
        "regulatory_sanctions_details": dd.regulatory_sanctions_details,
        "is_pep": dd.is_pep,
        "insolvency_history": dd.insolvency_history,
        "insolvency_history_details": dd.insolvency_history_details,
        "sufficient_financial_resources": dd.sufficient_financial_resources,
        "pending_legal_disputes": dd.pending_legal_disputes,
        "pending_legal_disputes_details": dd.pending_legal_disputes_details,
        "competitor_interest": dd.competitor_interest,
        "competitor_interest_details": dd.competitor_interest_details,
        "contractual_obligations": dd.contractual_obligations,
        "contractual_obligations_details": dd.contractual_obligations_details,
        "declared_truthful": dd.declared_truthful,
        "accepted_terms": dd.accepted_terms,
        "consented_aml": dd.consented_aml,
    }


@login_required
def applications_list(request):
    """Super-admin queue of coordinator / franchise account applications."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    base = User.objects.filter(GATED_ROLE_Q).select_related(
        "role", "primary_company", "application_decided_by"
    )

    pending = base.filter(application_status="submitted").order_by("-updated_at")
    approved = base.filter(application_status="approved").exclude(
        application_decided_at__isnull=True
    ).order_by("-application_decided_at")[:50]
    declined = base.filter(application_status="declined").order_by("-application_decided_at")[:50]

    # Attach due-diligence to the pending rows for inline review. NOTE: don't
    # use the name `due_diligence` — that's the reverse relation accessor for
    # the DueDiligence FK and Django rejects assigning a plain dict to it.
    pending = list(pending)
    for u in pending:
        u.dd_data = _serialize_due_diligence(u)

    return render(
        request,
        "dashboard/applications.html",
        {
            "active_menu": "applications",
            "pending": pending,
            "approved": approved,
            "declined": declined,
        },
    )


@login_required
@require_POST
@transaction.atomic
def application_action(request, user_id):
    """Super admin approves or declines a coordinator/franchise application."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "decline"):
        messages.error(request, "Invalid action.")
        return redirect("applications")

    applicant = get_object_or_404(
        User.objects.filter(GATED_ROLE_Q, application_status="submitted"),
        id=user_id,
    )

    applicant.application_decided_by = request.user
    applicant.application_decided_at = timezone.now()

    if decision == "approve":
        applicant.application_status = "approved"
        applicant.application_decline_reason = None
        applicant.save(update_fields=[
            "application_status", "application_decline_reason",
            "application_decided_by", "application_decided_at",
        ])
        success_msg = (
            f"Approved the application from "
            f"{applicant.first_name or ''} {applicant.last_name or applicant.email}.".strip()
        )
        approved = True
    else:
        applicant.application_status = "declined"
        applicant.application_decline_reason = (request.POST.get("decline_reason") or "").strip()
        applicant.save(update_fields=[
            "application_status", "application_decline_reason",
            "application_decided_by", "application_decided_at",
        ])
        success_msg = f"Declined the application from {applicant.email}."
        approved = False

    try:
        from accounts.utils.notifications import notify_application_decision
        notify_application_decision(applicant, approved=approved)
    except Exception:
        pass

    messages.success(request, success_msg)
    return redirect("applications")
