import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from django.db import models
from billing.models import Invoice, Subscription, CommercialPlan

logger = logging.getLogger("technical")


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


@login_required
def subscription_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    plans = CommercialPlan.objects.all()

    # Attach subscriber counts to each plan
    for plan in plans:
        plan.active_count = Subscription.objects.filter(plan=plan, status="active").count()
        plan.trial_count = Subscription.objects.filter(plan=plan, status="trial").count()
        plan.pending_count = Subscription.objects.filter(plan=plan, status="created").count()
        plan.total_count = Subscription.objects.filter(plan=plan).count()

    total_active = Subscription.objects.filter(status="active").count()
    total_revenue = Invoice.objects.filter(status="paid").aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    return render(request, "dashboard/subscriptions.html", {
        "plans": plans,
        "total_active": total_active,
        "total_revenue": total_revenue,
        "active_menu": "subscriptions",
    })


@login_required
@require_POST
def plan_toggle(request, plan_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    try:
        plan = get_object_or_404(CommercialPlan, id=plan_id)
        plan.is_active = not plan.is_active
        plan.save(update_fields=["is_active"])

        status = "activated" if plan.is_active else "deactivated"
        messages.success(request, f"Plan '{plan.name}' has been {status}.")
    except Exception as e:
        logger.error("Error toggling plan %s: %s", plan_id, e)
        messages.error(request, "Failed to update plan status.")

    return redirect("subscriptions")


@login_required
@require_POST
def plan_edit(request, plan_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    try:
        plan = get_object_or_404(CommercialPlan, id=plan_id)

        plan.name = request.POST.get("name", plan.name).strip()
        plan.tagline = request.POST.get("tagline", plan.tagline).strip()
        plan.best_for = request.POST.get("best_for", plan.best_for).strip()

        price = request.POST.get("price")
        if price:
            plan.price = round(float(price), 2)

        original_price = request.POST.get("original_price")
        if original_price:
            plan.original_price = round(float(original_price), 2)
        elif original_price == "":
            plan.original_price = None

        billing_period = request.POST.get("billing_period")
        if billing_period in ("monthly", "yearly"):
            plan.billing_period = billing_period

        plan.is_popular = request.POST.get("is_popular") == "on"

        features_raw = request.POST.get("features", "").strip()
        if features_raw:
            plan.features = [f.strip() for f in features_raw.split("\n") if f.strip()]
        else:
            plan.features = []

        plan.save()
        messages.success(request, f"Plan '{plan.name}' updated successfully.")

    except (ValueError, TypeError) as e:
        logger.error("Invalid data editing plan %s: %s", plan_id, e)
        messages.error(request, "Invalid data provided. Please check your input.")
    except Exception as e:
        logger.error("Error editing plan %s: %s", plan_id, e)
        messages.error(request, "Failed to update plan.")

    return redirect("subscriptions")
