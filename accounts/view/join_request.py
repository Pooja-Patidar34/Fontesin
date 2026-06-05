"""Profile-based "Join an existing company" flow.

A business user picks a company from their profile and sends a join request to
that company's owner. The owner approves or declines from the dedicated "Join
Requests" tab. On approval the requester is linked to the company via
UserCompany, so it appears in their My Companies and they can view its details.

This is deliberately separate from the partnership/CompanyConnection flow:
join requests are open to every business user (no paid-plan gate) and live in
their own owner-facing tab.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import (
    Company,
    CompanyJoinRequest,
    Notification,
    UserCompany,
)

# Roles that represent the single company they own/operate — the "join an
# existing company" concept doesn't apply to them (they register their own).
JOIN_BLOCKED_ROLES = {"consultant", "coordinator", "franchise"}


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _role_code(user):
    return (user.role.code or "").lower() if user.role else ""


class JoinRequestError(Exception):
    """Raised by create_join_request with a user-facing message + HTTP status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@transaction.atomic
def create_join_request(user, company, message=None):
    """Create (or re-open) a pending join request from ``user`` for ``company``
    and notify the company owner.

    Returns the CompanyJoinRequest. Raises JoinRequestError with a friendly
    message on any guard failure so callers can render it inline or as a toast.
    """
    if _role_code(user) in JOIN_BLOCKED_ROLES:
        raise JoinRequestError(
            "Your role represents a single company — please register your "
            "company instead of joining an existing one.",
            status=403,
        )

    if not company.is_active:
        raise JoinRequestError("That company is unavailable. Please pick another.")

    if company.owner_user_id == user.id:
        raise JoinRequestError("You already own this company.")

    # Already linked (own company at signup, an approved join, or an approved
    # partnership) — nothing to request.
    if UserCompany.objects.filter(user=user, company=company).exists():
        raise JoinRequestError(f"You're already linked to {company.name}.")

    req, created = CompanyJoinRequest.objects.get_or_create(
        user=user,
        company=company,
        defaults={"message": (message or "").strip() or None},
    )

    # Re-request after a decline: (user, company) is unique, so a declined row
    # lingers. Allow a fresh request by resetting it to pending. A still-pending
    # or already-approved row is left untouched (no spam / no downgrade).
    resent = False
    if not created:
        if req.status == CompanyJoinRequest.STATUS_PENDING:
            raise JoinRequestError(
                f"You already have a pending request to join {company.name}."
            )
        if req.status == CompanyJoinRequest.STATUS_APPROVED:
            raise JoinRequestError(f"You're already linked to {company.name}.")
        # declined → reopen
        req.status = CompanyJoinRequest.STATUS_PENDING
        req.reviewed_by = None
        req.reviewed_at = None
        new_msg = (message or "").strip() or None
        if new_msg is not None:
            req.message = new_msg
        req.save(update_fields=["status", "reviewed_by", "reviewed_at", "message", "updated_at"])
        resent = True

    # Notify the company owner that a join request is waiting.
    if company.owner_user_id and company.owner_user_id != user.id:
        try:
            from accounts.utils.notifications import notify

            requester_label = (
                f"{user.first_name} {user.last_name}".strip() or user.email
            )
            notify(
                recipient=company.owner_user,
                sender=user,
                kind=Notification.KIND_GENERIC,
                title=f"Join request from {requester_label}",
                body=(
                    f"{requester_label} has requested to join {company.name}. "
                    f"Open the Join Requests tab to approve or decline."
                ),
                link_url=reverse("join-requests"),
                related_company=company,
            )
        except Exception:
            pass

    return req


@login_required
@require_POST
def company_join(request, company_id):
    """Send a request to join an existing company straight from the Company
    Database "Action" menu — mirrors the profile "Join Existing Company" flow.
    Open to all business-user plans; owner approval is still required. All the
    guard rules (already owner / already linked / pending request / role) live
    in create_join_request and surface here as friendly messages."""
    company = get_object_or_404(Company, id=company_id)
    try:
        create_join_request(request.user, company)
        msg = (
            f"Join request sent to {company.name}. "
            f"You'll get access once the owner approves it."
        )
        if _is_ajax(request):
            return JsonResponse({"ok": True, "message": msg})
        messages.success(request, msg)
    except JoinRequestError as e:
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": e.message}, status=e.status)
        messages.error(request, e.message)
    return redirect(request.META.get("HTTP_REFERER") or "companies")


@login_required
def join_requests_list(request):
    """Owner-facing "Join Requests" tab.

    Shows incoming join requests on companies the current user owns (pending +
    decided history) plus the requests the current user has sent.
    """
    user = request.user

    outgoing = (
        CompanyJoinRequest.objects
        .filter(user=user)
        .select_related("company")
        .order_by("-created_at")
    )

    owned_company_ids = list(
        Company.objects.filter(owner_user=user).values_list("id", flat=True)
    )
    incoming = (
        CompanyJoinRequest.objects
        .filter(company_id__in=owned_company_ids)
        .select_related("user", "user__primary_company", "company")
        .order_by("-updated_at")
    )
    # Split incoming requests by status into their own tabs (Pending / Approved
    # / Declined). Decided rows are kept on file — they stay visible in the
    # Approved / Declined tabs and don't vanish when new requests arrive.
    incoming_pending = [r for r in incoming if r.status == CompanyJoinRequest.STATUS_PENDING]
    incoming_approved = [r for r in incoming if r.status == CompanyJoinRequest.STATUS_APPROVED]
    incoming_declined = [r for r in incoming if r.status == CompanyJoinRequest.STATUS_DECLINED]

    return render(
        request,
        "dashboard/join_requests.html",
        {
            "active_menu": "join-requests",
            "outgoing": outgoing,
            "incoming_pending": incoming_pending,
            "incoming_approved": incoming_approved,
            "incoming_declined": incoming_declined,
        },
    )


@login_required
@require_POST
@transaction.atomic
def join_request_action(request, request_id):
    """Approve or decline an incoming join request. Owner of the target
    company only. On approve the requester is linked via UserCompany."""
    decision = (request.POST.get("decision") or "").strip().lower()
    if decision not in ("approve", "decline"):
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": "Invalid action."}, status=400)
        messages.error(request, "Invalid action.")
        return redirect("join-requests")

    join_request = get_object_or_404(
        CompanyJoinRequest.objects.select_related("company", "user"),
        id=request_id,
        company__owner_user=request.user,
    )

    if join_request.status != CompanyJoinRequest.STATUS_PENDING:
        msg = f"This request was already {join_request.get_status_display().lower()}."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("join-requests")

    requester = join_request.user
    company = join_request.company
    owner = request.user

    if decision == "approve":
        join_request.status = CompanyJoinRequest.STATUS_APPROVED
        join_request.reviewed_by = owner
        join_request.reviewed_at = timezone.now()
        join_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

        # Grant access by linking the requester to the company. If they have no
        # primary company yet, adopt this one as primary (mirrors the old
        # instant-join onboarding) so the rest of the app has a tenant context.
        has_primary = bool(getattr(requester, "primary_company_id", None))
        UserCompany.objects.get_or_create(
            user=requester,
            company=company,
            defaults={"is_primary": not has_primary},
        )
        if not has_primary:
            requester.primary_company = company
            if company.tenant_id:
                requester.tenant = company.tenant
            requester.save(update_fields=["primary_company", "tenant", "updated_at"])
            # Backfill any consultant commissions that were skipped because the
            # user had no consultant-linked primary company at plan-approval
            # time — same as the create/join branches in profile_view.
            try:
                from billing.views import backfill_consultant_commissions_for_user
                backfill_consultant_commissions_for_user(requester)
            except Exception:
                pass

        msg = f"Approved {requester.email}'s request to join {company.name}."
    else:
        join_request.status = CompanyJoinRequest.STATUS_DECLINED
        join_request.reviewed_by = owner
        join_request.reviewed_at = timezone.now()
        join_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
        msg = f"Declined {requester.email}'s request to join {company.name}."

    # Tell the requester the verdict.
    try:
        from accounts.utils.notifications import notify

        owner_label = f"{owner.first_name} {owner.last_name}".strip() or owner.email
        if decision == "approve":
            title = f"You've joined {company.name}"
            body = (
                f"{owner_label} approved your request to join {company.name}. "
                f"It now appears in your My Companies."
            )
        else:
            title = f"Your request to join {company.name} was declined"
            body = f"{owner_label} declined your request to join {company.name}."
        notify(
            recipient=requester,
            sender=owner,
            kind=Notification.KIND_GENERIC,
            title=title,
            body=body,
            link_url=reverse("my-companies") if decision == "approve" else reverse("join-requests"),
            related_company=company,
        )
    except Exception:
        pass

    if _is_ajax(request):
        return JsonResponse({
            "ok": True,
            "status": join_request.status,
            "status_label": join_request.get_status_display(),
            "message": msg,
        })

    messages.success(request, msg)
    return redirect("join-requests")


@login_required
@require_POST
@transaction.atomic
def company_leave(request, company_id):
    """Leave (revoke) a company the user JOINED — used from the My Companies
    tab's "Leave" action on Member rows.

    Removes the UserCompany membership. If the company was the user's primary,
    reassign primary to another company they're still linked to, otherwise
    clear it. Any join-request record is deleted so they can request to join
    again later. Owners can't leave their own company.
    """
    user = request.user
    company = get_object_or_404(Company, id=company_id)

    if company.owner_user_id == user.id:
        msg = "You own this company, so you can't leave it."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("my-companies")

    link = UserCompany.objects.filter(user=user, company=company).first()
    if not link:
        msg = "You're not a member of this company."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("my-companies")

    link.delete()

    # Reassign primary if this was the user's primary company. Prefer a company
    # the user OWNS (created) — those may have no UserCompany row but are still
    # "theirs" — then fall back to any remaining joined membership, otherwise
    # clear it. Without the owned-company step the user could be left with no
    # primary (and the profile's "Set Up Your Company" prompt) despite still
    # owning a company.
    if user.primary_company_id == company.id:
        new_primary = (
            Company.objects.filter(owner_user=user).exclude(id=company.id).first()
        )
        if new_primary is None:
            other_link = (
                UserCompany.objects
                .filter(user=user)
                .exclude(company=company)
                .select_related("company")
                .first()
            )
            new_primary = other_link.company if other_link else None

        if new_primary is not None:
            user.primary_company = new_primary
            if new_primary.tenant_id:
                user.tenant = new_primary.tenant
            user.save(update_fields=["primary_company", "tenant", "updated_at"])
        else:
            user.primary_company = None
            user.save(update_fields=["primary_company", "updated_at"])

    # Drop any join-request record so a fresh request can be sent later.
    CompanyJoinRequest.objects.filter(user=user, company=company).delete()

    # Tell the company owner that this member left.
    if company.owner_user_id and company.owner_user_id != user.id:
        try:
            from accounts.utils.notifications import notify
            who = f"{user.first_name} {user.last_name}".strip() or user.email
            notify(
                recipient=company.owner_user,
                sender=user,
                kind=Notification.KIND_GENERIC,
                title=f"{who} left {company.name}",
                body=f"{who} has left your company {company.name}.",
                link_url=reverse("join-requests"),
                related_company=company,
            )
        except Exception:
            pass

    msg = f"You've left {company.name}."
    if _is_ajax(request):
        return JsonResponse({"ok": True, "message": msg})
    messages.success(request, msg)
    return redirect("my-companies")


@login_required
@require_POST
@transaction.atomic
def join_request_cancel(request, request_id):
    """Withdraw / remove a join request.

    - Requester may cancel a pending request (withdraw) or leave an approved
      company (which removes the UserCompany link).
    - Owner may revoke an approved request (also removes the link).
    Declined requests are final and not cancellable.
    """
    join_request = get_object_or_404(
        CompanyJoinRequest.objects.select_related("company", "user"),
        id=request_id,
    )

    is_requester = join_request.user_id == request.user.id
    is_owner = join_request.company.owner_user_id == request.user.id

    if not (is_requester or is_owner):
        msg = "You don't have permission to cancel this request."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=403)
        messages.error(request, msg)
        return redirect("join-requests")

    # Owner (not also the requester) may only revoke an approved request;
    # pending ones use approve/decline, declined ones are final.
    if is_owner and not is_requester and join_request.status != CompanyJoinRequest.STATUS_APPROVED:
        msg = "Only approved requests can be revoked. Use Decline for pending requests."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("join-requests")

    if is_requester and join_request.status == CompanyJoinRequest.STATUS_DECLINED:
        msg = "This request was declined and can't be cancelled."
        if _is_ajax(request):
            return JsonResponse({"ok": False, "message": msg}, status=400)
        messages.error(request, msg)
        return redirect("join-requests")

    company = join_request.company
    was_approved = join_request.status == CompanyJoinRequest.STATUS_APPROVED
    # Capture the parties before deleting the row so we can notify them after.
    requester = join_request.user
    owner = company.owner_user

    # Remove the membership the approval created. Keep is_primary=True rows —
    # that's the user's chosen primary company, not a join grant.
    if was_approved:
        UserCompany.objects.filter(
            user=join_request.user,
            company=company,
            is_primary=False,
        ).delete()

    join_request.delete()

    # Notify the affected party when an actual membership ends (an approved
    # request being revoked/left — not a pending withdrawal, where no one had
    # joined yet):
    #   * owner revokes  → tell the member their access was removed
    #   * member leaves  → tell the owner the member left
    if was_approved:
        try:
            from accounts.utils.notifications import notify
            if is_owner and not is_requester:
                owner_label = (
                    f"{owner.first_name} {owner.last_name}".strip() or owner.email
                ) if owner else "The company owner"
                notify(
                    recipient=requester,
                    sender=request.user,
                    kind=Notification.KIND_GENERIC,
                    title=f"Your access to {company.name} was removed",
                    body=(
                        f"{owner_label} removed your membership in {company.name}. "
                        f"You no longer have access to this company."
                    ),
                    link_url=reverse("my-companies"),
                    related_company=company,
                )
            elif is_requester and owner and owner.id != requester.id:
                who = f"{requester.first_name} {requester.last_name}".strip() or requester.email
                notify(
                    recipient=owner,
                    sender=requester,
                    kind=Notification.KIND_GENERIC,
                    title=f"{who} left {company.name}",
                    body=f"{who} has left your company {company.name}.",
                    link_url=reverse("join-requests"),
                    related_company=company,
                )
        except Exception:
            pass

    if was_approved:
        msg = f"Membership in {company.name} has been removed."
    else:
        msg = f"Join request to {company.name} has been withdrawn."

    if _is_ajax(request):
        return JsonResponse({"ok": True, "message": msg})

    messages.success(request, msg)
    return redirect("join-requests")
