import json
import logging
from datetime import datetime

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

# The admin Edit Plan form only exposes a "Mark as Most Popular" checkbox, not
# the underlying badge_text / badge_style fields. We treat is_popular as the
# source of truth for the popular badge so unchecking it actually removes the
# badge from the membership page. Other badges (e.g. "Best Value", which is
# stored on a non-popular plan) are preserved.
POPULAR_BADGE_TEXT = "⭐ Most Popular"
POPULAR_BADGE_STYLE = "primary"


@login_required
def invoice_list(request):
    is_business_user = (
        request.user.role
        and request.user.role.code
        and request.user.role.code.lower() == "business_user"
    )

    if not request.user.is_superuser and not is_business_user:
        raise PermissionDenied()

    qs = Invoice.objects.select_related(
        "subscription__user", "subscription__plan"
    ).order_by("-created_at")
    if not request.user.is_superuser:
        qs = qs.filter(subscription__user=request.user)

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

    qs = (
        Subscription.objects
        .select_related("user", "plan")
        .prefetch_related("invoice_set")
        .order_by("-created_at")
    )

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

    context = {
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "active_menu": "payments",
        "status_filter": status_filter,
        "pending_count": pending_count,
    }

    # AJAX: filter-tab and pagination clicks ask only for the inner panel.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "dashboard/_payments_panel.html", context)

    return render(request, "dashboard/payments.html", context)


@login_required
@require_POST
def payment_approve(request, subscription_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    sub = get_object_or_404(Subscription, id=subscription_id)

    if sub.status != "created":
        messages.warning(request, "This subscription is not pending approval.")
        return redirect("payments")

    now = timezone.now()

    # Supersede any other still-active subscription for this user (e.g. the
    # Free plan they were on before initiating this upgrade). Without this
    # the user ends up with two `active` rows and `get_active_subscription`
    # picks one with `.first()` and no ordering — the resulting plan tier is
    # effectively non-deterministic. Using "cancelled" because the existing
    # STATUS_CHOICES has no "superseded"/"expired" — closest fit.
    Subscription.objects.filter(
        user=sub.user, status="active"
    ).exclude(pk=sub.pk).update(
        status="cancelled", end_date=now, updated_at=now
    )

    sub.status = "active"
    sub.start_date = now
    sub.save(update_fields=["status", "start_date", "updated_at"])

    # Sync User.subscription_plan to the newly-active plan. select_plan
    # intentionally defers this write for paid upgrades; this is the
    # promotion point.
    user = sub.user
    new_plan_code = (sub.plan.code or "").lower() if sub.plan_id else ""
    if new_plan_code and user.subscription_plan != new_plan_code:
        user.subscription_plan = new_plan_code
        user.save(update_fields=["subscription_plan"])

    # Mark the related invoice as paid
    Invoice.objects.filter(subscription=sub, status="pending").update(
        status="paid", paid_at=now
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
def payment_detail_ajax(request, subscription_id):
    """Return subscription data as JSON for the edit modal."""
    if not request.user.is_superuser:
        return JsonResponse({"error": "forbidden"}, status=403)

    sub = get_object_or_404(
        Subscription.objects.select_related("user", "plan"), id=subscription_id
    )
    plans = list(
        CommercialPlan.objects.filter(is_active=True)
        .order_by("sort_order")
        .values("id", "code", "name")
    )
    return JsonResponse({
        "id": sub.id,
        "user_email": sub.user.email if sub.user else "-",
        "plan_id": sub.plan_id,
        "status": sub.status,
        "start_date": sub.start_date.strftime("%Y-%m-%d") if sub.start_date else "",
        "end_date": sub.end_date.strftime("%Y-%m-%d") if sub.end_date else "",
        "plans": plans,
    })


@login_required
@require_POST
def payment_edit(request, subscription_id):
    """Update subscription plan, status, and dates."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    sub = get_object_or_404(Subscription, id=subscription_id)

    plan_id = request.POST.get("plan_id")
    status = request.POST.get("status")
    end_date = request.POST.get("end_date")

    if plan_id:
        plan = get_object_or_404(CommercialPlan, id=plan_id, is_active=True)
        sub.plan = plan
        if sub.user:
            sub.user.subscription_plan = plan.code
            sub.user.save(update_fields=["subscription_plan"])

    if status and status in dict(Subscription.STATUS_CHOICES):
        old_status = sub.status
        sub.status = status
        # If changing to active, mark invoice as paid
        if status == "active" and old_status != "active":
            Invoice.objects.filter(subscription=sub, status="pending").update(
                status="paid", paid_at=timezone.now()
            )

    if end_date:
        try:
            sub.end_date = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d"))
        except ValueError:
            pass

    sub.save()
    messages.success(request, f"Subscription for {sub.user.email} updated successfully.")
    return redirect("payments")


@login_required
def subscription_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied()

    plans_qs = CommercialPlan.objects.annotate(
        active_count=models.Count("subscription", filter=models.Q(subscription__status="active")),
        trial_count=models.Count("subscription", filter=models.Q(subscription__status="trial")),
        pending_count=models.Count("subscription", filter=models.Q(subscription__status="created")),
        total_count=models.Count("subscription"),
    ).order_by("id")

    total_active = Subscription.objects.filter(status="active").count()
    total_revenue = Invoice.objects.filter(status="paid").aggregate(
        total=models.Sum("amount")
    )["total"] or 0

    paginator = Paginator(plans_qs, 10)
    total_plans = paginator.count
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, "dashboard/subscriptions.html", {
        "plans": page_obj,
        "page_obj": page_obj,
        "total_plans": total_plans,
        "total_active": total_active,
        "total_revenue": total_revenue,
        "active_menu": "subscriptions",
    })


@login_required
@require_POST
def plan_toggle(request, plan_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        plan = get_object_or_404(CommercialPlan, id=plan_id)
        plan.is_active = not plan.is_active
        plan.save(update_fields=["is_active"])

        status = "activated" if plan.is_active else "deactivated"
        msg = f"Plan '{plan.name}' has been {status}."

        if is_ajax:
            return JsonResponse({
                "ok": True,
                "is_active": plan.is_active,
                "message": msg,
            })

        messages.success(request, msg)
    except Exception as e:
        logger.error("Error toggling plan %s: %s", plan_id, e)
        if is_ajax:
            return JsonResponse({"ok": False, "message": "Failed to update plan status."}, status=500)
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

        mark_popular = request.POST.get("is_popular") == "on"
        plan.is_popular = mark_popular
        if mark_popular:
            # Re-apply the popular badge so the membership page shows it.
            plan.badge_text = POPULAR_BADGE_TEXT
            plan.badge_style = POPULAR_BADGE_STYLE
        elif (
            plan.badge_text == POPULAR_BADGE_TEXT
            or plan.badge_style == POPULAR_BADGE_STYLE
        ):
            # Was the popular plan, now isn't — clear the badge so it stops
            # rendering. Don't touch other badges (e.g. "Best Value") attached
            # to non-popular plans.
            plan.badge_text = ""
            plan.badge_style = ""

        # Features are entered as one per line. A leading "-" or "x" marks
        # the feature as NOT included (renders the X icon). Stored as a list
        # of dicts so the membership template can show check / cross icons.
        features_raw = request.POST.get("features", "").strip()
        if features_raw:
            features = []
            for line in features_raw.split("\n"):
                text = line.strip()
                if not text:
                    continue
                included = True
                if text.startswith(("-", "x", "X", "✗")):
                    included = False
                    text = text.lstrip("-xX✗").strip()
                features.append({"included": included, "text": text})
            plan.features = features
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
