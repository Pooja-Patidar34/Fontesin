from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.models import Invoice, Subscription


@login_required
def invoice_list(request):
    is_business_user = (
        request.user.role
        and request.user.role.code
        and request.user.role.code.lower() == "business_user"
    )

    if not request.user.is_superuser and not is_business_user:
        raise PermissionDenied()

    if request.user.is_superuser:
        qs = Invoice.objects.select_related(
            "subscription__user", "subscription__plan"
        ).order_by("-created_at")
    else:
        qs = Invoice.objects.filter(
            subscription__user=request.user
        ).select_related(
            "subscription__user", "subscription__plan"
        ).order_by("-created_at")

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "dashboard/invoices.html", {
        "invoices": page_obj,
        "page_obj": page_obj,
        "active_menu": "invoices",
    })


@login_required
def payment_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    status_filter = request.GET.get("status", "all")

    qs = Subscription.objects.select_related("user", "plan").order_by("-created_at")

    if status_filter == "pending":
        qs = qs.filter(status="created")
    elif status_filter == "approved":
        qs = qs.filter(status="active")
    elif status_filter == "rejected":
        qs = qs.filter(status="cancelled")

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    # Count pending for badge
    pending_count = Subscription.objects.filter(status="created").count()

    return render(request, "dashboard/payments.html", {
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "active_menu": "payments",
        "status_filter": status_filter,
        "pending_count": pending_count,
    })


@login_required
@require_POST
def payment_approve(request, subscription_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    sub = get_object_or_404(Subscription, id=subscription_id)

    if sub.status != "created":
        messages.warning(request, "This subscription is not pending approval.")
        return redirect("payments")

    sub.status = "active"
    sub.start_date = timezone.now()
    sub.save(update_fields=["status", "start_date", "updated_at"])

    # Mark the related invoice as paid
    Invoice.objects.filter(subscription=sub, status="pending").update(
        status="paid", paid_at=timezone.now()
    )

    messages.success(request, f"Subscription for {sub.user.email} has been approved.")
    return redirect("payments")


@login_required
@require_POST
def payment_reject(request, subscription_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    sub = get_object_or_404(Subscription, id=subscription_id)

    if sub.status != "created":
        messages.warning(request, "This subscription is not pending approval.")
        return redirect("payments")

    sub.status = "cancelled"
    sub.save(update_fields=["status", "updated_at"])

    # Mark the related invoice as failed
    Invoice.objects.filter(subscription=sub, status="pending").update(status="failed")

    messages.success(request, f"Subscription for {sub.user.email} has been rejected.")
    return redirect("payments")
