from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import Company, CompanyConnection, UserCompany
from accounts.view.saved_filter import _require_paid_business_user


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@login_required
def partnership_list(request):
    """
    Partnership tab — paid business users (basic, pro, global).

    Shows two halves:
      • Incoming requests on companies the current user owns (approve / reject).
      • Outgoing requests the current user has sent to other companies.
    """
    _require_paid_business_user(request.user)

    outgoing = (
        CompanyConnection.objects
        .filter(user=request.user)
        .select_related("company")
    )

    owned_company_ids = list(
        Company.objects.filter(owner_user=request.user).values_list("id", flat=True)
    )
    # `user__primary_company` so the incoming view can show the requester's
    # company (the relevant "who's asking to partner") instead of the owner's
    # own company (which the owner already knows).
    incoming = (
        CompanyConnection.objects
        .filter(company_id__in=owned_company_ids)
        .select_related("user", "user__primary_company", "company")
    )

    incoming_pending = [c for c in incoming if c.status == CompanyConnection.STATUS_PENDING]
    incoming_history = [c for c in incoming if c.status != CompanyConnection.STATUS_PENDING]

    return render(
        request,
        "dashboard/partnerships.html",
        {
            "active_menu": "partnerships",
            "outgoing": outgoing,
            "incoming_pending": incoming_pending,
            "incoming_history": incoming_history,
        },
    )


@login_required
@require_POST
@transaction.atomic
def partnership_action(request, connection_id):
    """
    Approve or reject an incoming connection request.

    Only the owner of the target company (on a paid plan) may act. On approve,
    the requesting user is linked to the company via UserCompany so they can
    view its data per the system's permission rules.
    """
    _require_paid_business_user(request.user)

    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "reject"):
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": "Invalid action."}, status=400)
        messages.error(request, "Invalid action.")
        return redirect("partnerships")

    connection = get_object_or_404(
        CompanyConnection.objects.select_related("company", "user"),
        id=connection_id,
        company__owner_user=request.user,
    )

    if connection.status != CompanyConnection.STATUS_PENDING:
        msg = f"This request was already {connection.get_status_display().lower()}."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("partnerships")

    if decision == "approve":
        connection.status = CompanyConnection.STATUS_ACCEPTED
        connection.save(update_fields=["status", "updated_at"])
        # Grant access by linking the requesting user to the company. is_primary
        # stays False — the user's chosen primary company should not change here.
        UserCompany.objects.get_or_create(
            user=connection.user,
            company=connection.company,
            defaults={"is_primary": False},
        )
        msg = (
            f"Approved {connection.user.email}'s request to connect with "
            f"{connection.company.name}."
        )
    else:
        connection.status = CompanyConnection.STATUS_REJECTED
        connection.save(update_fields=["status", "updated_at"])
        msg = (
            f"Rejected {connection.user.email}'s request to connect with "
            f"{connection.company.name}."
        )

    if _is_ajax(request):
        return JsonResponse({
            "ok": True,
            "status": connection.status,
            "status_label": connection.get_status_display(),
            "message": msg,
        })

    messages.success(request, msg)
    return redirect(reverse("partnerships"))


@login_required
@require_POST
@transaction.atomic
def partnership_cancel(request, connection_id):
    """
    Cancel a partnership from either side.

    - Sender (connection.user) can cancel a pending request (withdraw) or an
      accepted one (disconnect).
    - Receiver (company.owner_user) can revoke an accepted partnership.
    Rejected partnerships are not cancellable — that's already a final state.

    On cancel of an accepted partnership we also remove the UserCompany row
    that approval created, so the requester loses view access cleanly.
    """
    connection = get_object_or_404(
        CompanyConnection.objects.select_related("company", "user"),
        id=connection_id,
    )

    is_sender = connection.user_id == request.user.id
    is_receiver = connection.company.owner_user_id == request.user.id

    if not (is_sender or is_receiver):
        msg = "You don't have permission to cancel this partnership."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect("partnerships")

    # Receiver may only cancel partnerships they actively approved. Pending
    # requests on their company use approve/reject; rejected ones are final.
    if is_receiver and not is_sender:
        if connection.status != CompanyConnection.STATUS_ACCEPTED:
            msg = (
                "Only accepted partnerships can be revoked. Use Reject for "
                "pending requests."
            )
            if _is_ajax(request):
                return JsonResponse({"ok": False, "message": msg}, status=400)
            messages.error(request, msg)
            return redirect("partnerships")

    # Sender may cancel pending or accepted, but not rejected (the decision
    # was made and isn't theirs to undo).
    if is_sender and connection.status == CompanyConnection.STATUS_REJECTED:
        msg = "This request was rejected and can't be cancelled."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("partnerships")

    company_name = connection.company.name
    was_accepted = connection.status == CompanyConnection.STATUS_ACCEPTED

    # If approval had granted view access via UserCompany, remove it. Keep
    # primary linkages (is_primary=True) — those represent the user's chosen
    # primary company at signup, not a partnership grant.
    if was_accepted:
        UserCompany.objects.filter(
            user=connection.user,
            company=connection.company,
            is_primary=False,
        ).delete()

    connection.delete()

    if was_accepted:
        msg = f"Partnership with {company_name} has been ended."
    else:
        msg = f"Connection request to {company_name} has been cancelled."

    if _is_ajax(request):
        return JsonResponse({"ok": True, "message": msg})

    messages.success(request, msg)
    return redirect(reverse("partnerships"))
