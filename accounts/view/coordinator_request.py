"""Business User → Coordinator upgrade workflow.

A Business User submits a request from their profile page. The request goes
to every active Super Admin, who can Approve or Decline. On approval the
user's role is switched to COORDINATOR (primary_company linkage is kept).
On decline the user remains a Business User; the decline reason is surfaced
back to them on the profile page.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _

from accounts.models import CoordinatorRequest, Role, User


def _role_code(user):
    if user.is_superuser:
        return "superuser"
    return (user.role.code or "").upper() if user.role else ""


def _is_business_user(user):
    return _role_code(user) == "BUSINESS_USER"


@login_required
@require_POST
@transaction.atomic
def coordinator_request_submit(request):
    """BU submits a coordinator upgrade request from their profile page."""
    if not _is_business_user(request.user):
        raise PermissionDenied("Only Business Users can request to become a Coordinator.")

    existing_pending = CoordinatorRequest.objects.filter(
        user=request.user, status=CoordinatorRequest.STATUS_PENDING
    ).exists()
    if existing_pending:
        messages.info(
            request,
            _("You already have a pending coordinator request. Please wait for the Super Admin's decision."),
        )
        return redirect("profile")

    target_region = (request.POST.get("target_region") or "").strip()[:200]
    motivation = (request.POST.get("motivation") or "").strip()

    # Target region is now a required dropdown selection — it determines the
    # region the coordinator will manage once approved.
    if not target_region:
        messages.error(request, _("Please select the target region you want to coordinate."))
        return redirect("profile")

    coord_request = CoordinatorRequest.objects.create(
        user=request.user,
        status=CoordinatorRequest.STATUS_PENDING,
        target_region=target_region,
        motivation=motivation,
    )

    try:
        from accounts.utils.notifications import notify_coordinator_request_submitted
        notify_coordinator_request_submitted(coord_request)
    except Exception:
        pass

    messages.success(
        request,
        _("Your request to become a Coordinator has been submitted. "
          "The Super Admin will review it shortly."),
    )
    return redirect("profile")


@login_required
def coordinator_requests_list(request):
    """Super Admin queue of coordinator role requests."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    pending = (
        CoordinatorRequest.objects.filter(status=CoordinatorRequest.STATUS_PENDING)
        .select_related("user", "user__role", "user__primary_company")
        .order_by("-created_at")
    )
    approved = (
        CoordinatorRequest.objects.filter(status=CoordinatorRequest.STATUS_APPROVED)
        .select_related("user", "decided_by")
        .order_by("-decided_at")[:50]
    )
    declined = (
        CoordinatorRequest.objects.filter(status=CoordinatorRequest.STATUS_DECLINED)
        .select_related("user", "decided_by")
        .order_by("-decided_at")[:50]
    )

    return render(
        request,
        "dashboard/coordinator_requests.html",
        {
            "active_menu": "coordinator-requests",
            "pending": pending,
            "approved": approved,
            "declined": declined,
        },
    )


@login_required
@require_POST
@transaction.atomic
def coordinator_request_action(request, request_id):
    """Super Admin approves or declines a coordinator role request."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "decline"):
        messages.error(request, _("Invalid action."))
        return redirect("coordinator-requests")

    coord_request = get_object_or_404(
        CoordinatorRequest.objects.filter(status=CoordinatorRequest.STATUS_PENDING),
        id=request_id,
    )

    coord_request.decided_by = request.user
    coord_request.decided_at = timezone.now()

    if decision == "approve":
        coordinator_role = Role.objects.filter(code__iexact="coordinator").first()
        if not coordinator_role:
            messages.error(
                request,
                _("Coordinator role is not configured. Create the Coordinator role before approving."),
            )
            return redirect("coordinator-requests")

        requester = coord_request.user
        requester.role = coordinator_role
        # Carry the requested region onto the new coordinator so their Company
        # Database is scoped to that region (coordinator_territory_q resolves
        # the region from target_region when no explicit territory_country is
        # set — same as a coordinator who signed up via the registration flow).
        update_fields = ["role"]
        if coord_request.target_region and not (requester.target_region or "").strip():
            requester.target_region = coord_request.target_region
            update_fields.append("target_region")
        requester.save(update_fields=update_fields)

        coord_request.status = CoordinatorRequest.STATUS_APPROVED
        coord_request.save(update_fields=[
            "status", "decided_by", "decided_at", "updated_at"
        ])
        requester_label = (
            f"{requester.first_name or ''} {requester.last_name or requester.email}".strip()
        )
        success_msg = _("Approved coordinator role for %(name)s.") % {"name": requester_label}
        approved = True
    else:
        coord_request.status = CoordinatorRequest.STATUS_DECLINED
        coord_request.decline_reason = (request.POST.get("decline_reason") or "").strip()
        coord_request.save(update_fields=[
            "status", "decided_by", "decided_at", "decline_reason", "updated_at"
        ])
        success_msg = _("Declined coordinator request from %(email)s.") % {
            "email": coord_request.user.email
        }
        approved = False

    try:
        from accounts.utils.notifications import notify_coordinator_request_decision
        notify_coordinator_request_decision(coord_request, approved=approved)
    except Exception:
        pass

    messages.success(request, success_msg)
    return redirect("coordinator-requests")


def pending_coordinator_request_count(user):
    """Used by the navbar context processor to render the sidebar badge for
    Super Admins. Returns 0 for everyone else."""
    if not user.is_authenticated or not user.is_superuser:
        return 0
    return CoordinatorRequest.objects.filter(
        status=CoordinatorRequest.STATUS_PENDING
    ).count()
