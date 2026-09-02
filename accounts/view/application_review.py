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
from django.utils.translation import gettext as _

from accounts.models import User, DueDiligence


# Roles that go through super-admin application approval. Imported from the
# middleware so the gate, the pending screen, and this review queue share ONE
# source of truth — duplicating it here is exactly what caused a dashboard ⇆
# application-pending redirect loop when consultants were added to the gate.
# Role codes are stored case-insensitively in the DB, so match with iexact.
from FontEsin.middleware.require_application_approval import GATED_ROLE_CODES

_gated_role_qs = [Q(role__code__iexact=_c) for _c in GATED_ROLE_CODES]
GATED_ROLE_Q = _gated_role_qs[0]
for _q in _gated_role_qs[1:]:
    GATED_ROLE_Q |= _q


def _role_code(user):
    return (user.role.code or "").lower() if user.role else ""


# Which queue reviews a registration application, by the role the person signed
# up under. Sign-ups used to pile into one "Staff Applications" list while
# Coordinator Requests and Franchise Requests sat next to it holding the OTHER
# half of the same conversation — an admin had to know that a coordinator could
# arrive through either door. Each role's requests now land in that role's own
# tab, whichever way they came in (Sep 2026).
QUEUE_BY_ROLE = {
    "consultant": "consultant-requests",
    "coordinator": "coordinator-requests",
}
# Everything else (currently the franchise role) stays on the general queue.
DEFAULT_QUEUE = "applications"


def staff_applications(role_codes):
    """Registration applications for `role_codes`, split by decision state.

    One definition for every queue that shows sign-ups, so the tabs cannot drift
    apart in what they consider pending. `role_codes` is matched case-insensitively
    because role codes are stored inconsistently cased.
    """
    role_q = Q()
    for code in role_codes:
        role_q |= Q(role__code__iexact=code)

    base = User.objects.filter(role_q).select_related(
        "role", "primary_company", "application_decided_by",
    )
    pending = list(base.filter(application_status="submitted").order_by("-updated_at"))
    for user in pending:
        # NOTE: don't use the name `due_diligence` — that's the reverse relation
        # accessor for the DueDiligence FK and Django rejects assigning a plain
        # dict to it.
        user.dd_data = _serialize_due_diligence(user)
    return {
        "pending": pending,
        "approved": list(
            base.filter(application_status="approved")
            .exclude(application_decided_at__isnull=True)
            .order_by("-application_decided_at")[:50]
        ),
        "declined": list(
            base.filter(application_status="declined")
            .order_by("-application_decided_at")[:50]
        ),
    }


@login_required
def consultant_requests_list(request):
    """Super-admin queue of consultant registration applications.

    Consultants have no separate "upgrade" request the way coordinators do, so
    this queue is exactly the sign-ups — but it is their own tab, so an admin
    looking for consultant requests finds them where the name says they are.
    """
    if not request.user.is_superuser:
        raise PermissionDenied()

    rows = staff_applications(["consultant"])
    return render(
        request,
        "dashboard/consultant_requests.html",
        {
            "active_menu": "consultant-requests",
            "signup_pending": rows["pending"],
            "signup_approved": rows["approved"],
            "signup_declined": rows["declined"],
        },
    )


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

    # Only the roles without a queue of their own — consultant and coordinator
    # sign-ups now go to their own tabs (see QUEUE_BY_ROLE), so a role's requests
    # appear in exactly one place instead of two.
    own_queue_roles = set(QUEUE_BY_ROLE)
    rows = staff_applications([c for c in GATED_ROLE_CODES if c not in own_queue_roles])

    return render(
        request,
        "dashboard/applications.html",
        {
            "active_menu": "applications",
            "pending": rows["pending"],
            "approved": rows["approved"],
            "declined": rows["declined"],
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
        messages.error(request, _("Invalid action."))
        return redirect("applications")

    applicant = get_object_or_404(
        User.objects.filter(GATED_ROLE_Q, application_status="submitted"),
        id=user_id,
    )
    # Back to the queue this application is listed in, so the admin returns to
    # the tab they acted from rather than being dropped on the general list.
    back = QUEUE_BY_ROLE.get(_role_code(applicant), DEFAULT_QUEUE)

    applicant.application_decided_by = request.user
    applicant.application_decided_at = timezone.now()

    if decision == "approve":
        applicant.application_status = "approved"
        applicant.application_decline_reason = None
        applicant.save(update_fields=[
            "application_status", "application_decline_reason",
            "application_decided_by", "application_decided_at",
        ])
        applicant_label = (
            f"{applicant.first_name or ''} {applicant.last_name or applicant.email}".strip()
        )
        success_msg = _("Approved the application from %(name)s.") % {"name": applicant_label}
        approved = True
    else:
        applicant.application_status = "declined"
        applicant.application_decline_reason = (request.POST.get("decline_reason") or "").strip()
        applicant.save(update_fields=[
            "application_status", "application_decline_reason",
            "application_decided_by", "application_decided_at",
        ])
        success_msg = _("Declined the application from %(email)s.") % {"email": applicant.email}
        approved = False

    try:
        from accounts.utils.notifications import notify_application_decision
        notify_application_decision(applicant, approved=approved)
    except Exception:
        pass

    messages.success(request, success_msg)
    return redirect(back)
