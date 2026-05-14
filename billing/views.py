import json
import logging
from datetime import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from django.db import models
from billing.models import Invoice, Subscription, CommercialPlan, ConsultantCommission

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
def plan_history(request):
    """Timeline of subscriptions for the logged-in business user.

    Shows every Subscription row tied to the user, including past ones
    (status=cancelled with end_date set) and the current active/trial one.
    Superusers see all subscriptions across the platform for support cases.
    """
    is_business_user = (
        request.user.role
        and request.user.role.code
        and request.user.role.code.lower() == "business_user"
    )

    if not request.user.is_superuser and not is_business_user:
        raise PermissionDenied()

    qs = (
        Subscription.objects
        .select_related("plan", "user")
        .order_by("-start_date", "-created_at")
    )
    if not request.user.is_superuser:
        qs = qs.filter(user=request.user)

    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "dashboard/plan_history.html", {
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "active_menu": "plan-history",
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

    # Consultant commission: 10% to the consultant whose company the business
    # user is currently linked to as their primary. Skipped for the Free plan
    # (no real revenue), for users with no primary_company, and for companies
    # whose `consultant` FK is unset. The unique (consultant, subscription)
    # constraint makes this idempotent — re-approval can never double-pay.
    _maybe_create_commission(sub, now)

    messages.success(request, f"Subscription for {sub.user.email} has been approved.")
    return redirect("payments")


@login_required
def commission_list(request):
    """Earnings page. Consultants see only their own rows; superusers see all
    rows across the platform (for payout review)."""
    is_consultant = (
        request.user.role
        and request.user.role.code
        and request.user.role.code.lower() == "consultant"
    )
    if not request.user.is_superuser and not is_consultant:
        raise PermissionDenied()

    qs = (
        ConsultantCommission.objects
        .select_related("consultant", "business_user", "company", "subscription__plan", "invoice")
        .order_by("-created_at")
    )
    if not request.user.is_superuser:
        qs = qs.filter(consultant=request.user)

    status_filter = (request.GET.get("status") or "").strip().lower()
    if status_filter in {"pending", "paid", "cancelled"}:
        qs = qs.filter(status=status_filter)

    # Totals per currency — a consultant may earn in USD and EUR from
    # different business users, so sum is meaningless without a currency split.
    totals_by_currency = {}
    pending_by_currency = {}
    admin_totals_by_currency = {}
    for row in qs:
        totals_by_currency[row.currency] = totals_by_currency.get(row.currency, Decimal("0")) + row.commission_amount
        admin_totals_by_currency[row.currency] = admin_totals_by_currency.get(row.currency, Decimal("0")) + row.admin_share
        if row.status == "pending":
            pending_by_currency[row.currency] = pending_by_currency.get(row.currency, Decimal("0")) + row.commission_amount

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(request, "dashboard/commissions.html", {
        "commissions": page_obj,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "active_menu": "commissions",
        "totals_by_currency": totals_by_currency,
        "pending_by_currency": pending_by_currency,
        "admin_totals_by_currency": admin_totals_by_currency,
        "viewing_as_admin": request.user.is_superuser,
    })


@login_required
def commission_invoice_detail_ajax(request, commission_id):
    """Renders the invoice block for a commission row inside the commissions
    modal. Visible to the admin and to the consultant who earned the
    commission — they need to see what the business user was billed."""
    commission = get_object_or_404(
        ConsultantCommission.objects.select_related(
            "consultant",
            "business_user",
            "company",
            "subscription__plan",
            "subscription__user",
            "invoice",
        ),
        id=commission_id,
    )
    if not request.user.is_superuser and commission.consultant_id != request.user.id:
        raise PermissionDenied()

    invoice = commission.invoice
    if invoice is None:
        return render(
            request,
            "dashboard/_commission_invoice_modal.html",
            {"commission": commission, "invoice": None},
        )

    bank = invoice.bank_snapshot or {}
    sender = invoice.sender_snapshot or {}

    invoice_currency = (invoice.currency or "USD").upper()
    if invoice.fx_rate is not None:
        display_amount = invoice.amount
        display_currency = invoice_currency
        fx_rate = invoice.fx_rate
        fx_source_currency = invoice.fx_source_currency or None
        fx_source_amount = invoice.fx_source_amount
    else:
        display_amount = invoice.amount
        display_currency = invoice_currency
        fx_rate = None
        fx_source_currency = None
        fx_source_amount = None

    return render(
        request,
        "dashboard/_commission_invoice_modal.html",
        {
            "commission": commission,
            "invoice": invoice,
            "bank": bank,
            "sender": sender,
            "display_amount": display_amount,
            "display_currency": display_currency,
            "fx_rate": fx_rate,
            "fx_source_currency": fx_source_currency,
            "fx_source_amount": fx_source_amount,
        },
    )


@login_required
def commission_invoice_export(request, commission_id):
    """Formatted XLSX download of a single commission's invoice.

    Layout:
      • Title banner with FONTESIN + invoice number.
      • Sectioned tables (Invoice / Subscriber / Plan / Total / Commission)
        each with a dark header row, alternating-color body rows, and
        thin borders so it reads as a proper invoice in Excel rather
        than a raw key/value dump.

    Access: same gate as ``commission_invoice_detail_ajax`` — admin or
    the consultant who earned the commission. Anyone else gets 403.
    """
    commission = get_object_or_404(
        ConsultantCommission.objects.select_related(
            "consultant",
            "business_user",
            "company",
            "subscription__plan",
            "subscription__user",
            "invoice",
        ),
        id=commission_id,
    )
    if not request.user.is_superuser and commission.consultant_id != request.user.id:
        raise PermissionDenied()

    invoice = commission.invoice
    sub = commission.subscription
    business_user = commission.business_user or (sub.user if sub else None)
    company = commission.company or (
        getattr(business_user, "primary_company", None) if business_user else None
    )

    inv_number = invoice.invoice_number if invoice else f"commission-{commission.id}"
    safe_inv = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(inv_number))
    filename = f"invoice-{safe_inv}.xlsx"

    # ---- Styles ----
    DARK = "253D51"
    LIGHT = "EAF2F7"
    ALT = "F8FAFC"
    GREEN = "DCFCE7"
    title_font = Font(name="Calibri", size=18, bold=True, color="FFFFFF")
    section_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    label_font = Font(name="Calibri", size=10, bold=True, color="253D51")
    value_font = Font(name="Calibri", size=10, color="1B2E3F")
    total_font = Font(name="Calibri", size=14, bold=True, color="166534")
    title_fill = PatternFill("solid", fgColor=DARK)
    section_fill = PatternFill("solid", fgColor=DARK)
    light_fill = PatternFill("solid", fgColor=LIGHT)
    alt_fill = PatternFill("solid", fgColor=ALT)
    total_fill = PatternFill("solid", fgColor=GREEN)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right = Alignment(horizontal="right", vertical="center")
    thin = Side(border_style="thin", color="C7D2DC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = Workbook()
    ws = wb.active
    ws.title = "Invoice"

    # Column widths
    widths = [22, 30, 22, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    row = 1

    def title_banner(text, height=32):
        nonlocal row
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        cell = ws.cell(row=row, column=1, value=text)
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        ws.row_dimensions[row].height = height
        row += 1

    def section_header(text):
        nonlocal row
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        cell = ws.cell(row=row, column=1, value=text)
        cell.font = section_font
        cell.fill = section_fill
        cell.alignment = left
        ws.row_dimensions[row].height = 22
        row += 1

    def kv_pair(label, value, alt=False):
        """Render two key/value pairs side by side, one in cols A:B, one in C:D.
        Pass `value` as None to leave the right pair blank."""
        nonlocal row
        fill = alt_fill if alt else light_fill
        # Pre-set fills + borders on all four cells so merged regions still
        # render with a continuous background.
        for col in range(1, 5):
            c = ws.cell(row=row, column=col)
            c.fill = fill
            c.border = border
        a = ws.cell(row=row, column=1, value=label)
        b = ws.cell(row=row, column=2, value=value)
        a.font = label_font
        a.alignment = left
        b.font = value_font
        b.alignment = left
        # Empty right half — merge B-D so single values can span when desired
        row += 1

    def kv_row(label1, value1, label2, value2, alt=False):
        nonlocal row
        fill = alt_fill if alt else light_fill
        for col in range(1, 5):
            c = ws.cell(row=row, column=col)
            c.fill = fill
            c.border = border
        a = ws.cell(row=row, column=1, value=label1)
        b = ws.cell(row=row, column=2, value=value1)
        c = ws.cell(row=row, column=3, value=label2)
        d = ws.cell(row=row, column=4, value=value2)
        a.font = label_font
        c.font = label_font
        b.font = value_font
        d.font = value_font
        a.alignment = left
        c.alignment = left
        b.alignment = left
        d.alignment = left
        row += 1

    def spacer():
        nonlocal row
        ws.row_dimensions[row].height = 6
        row += 1

    def total_row(label, amount):
        nonlocal row
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=4)
        a = ws.cell(row=row, column=1, value=label)
        b = ws.cell(row=row, column=3, value=amount)
        for col in (1, 2, 3, 4):
            c = ws.cell(row=row, column=col)
            c.fill = total_fill
            c.border = border
        a.font = total_font
        a.alignment = left
        b.font = total_font
        b.alignment = right
        ws.row_dimensions[row].height = 28
        row += 1

    # ---- Helpers for value formatting ----
    def fmt_date(dt):
        return dt.strftime("%B %d, %Y") if dt else "—"

    def fmt_currency(amount, currency):
        if amount is None:
            return "—"
        return f"{amount:,.2f} {currency or ''}".strip()

    plan_name = sub.plan.name if sub and sub.plan else "—"
    billing_period = (
        "Monthly" if sub and sub.plan and sub.plan.billing_period == "monthly"
        else "Annual" if sub and sub.plan else "—"
    )
    sub_user_name = (
        f"{business_user.first_name} {business_user.last_name}".strip()
        if business_user else "—"
    )
    sub_user_role = (
        business_user.role.name if business_user and business_user.role else "—"
    )

    # ---- Build the workbook ----
    title_banner(f"FONTESIN  ·  Invoice {inv_number}", height=36)
    spacer()

    section_header("Invoice")
    kv_row("Invoice Number", inv_number, "Status", (invoice.status if invoice else "—").upper(), alt=False)
    kv_row(
        "Issue Date",
        fmt_date(invoice.created_at) if invoice else "—",
        "Paid At",
        fmt_date(invoice.paid_at) if invoice and invoice.paid_at else "—",
        alt=True,
    )
    if invoice and invoice.status != "paid" and invoice.due_date:
        kv_row("Due Date", fmt_date(invoice.due_date), "", "", alt=False)
    spacer()

    section_header("Subscriber")
    kv_row("Name", sub_user_name, "Email", business_user.email if business_user else "—", alt=False)
    kv_row("Role", sub_user_role, "Company", company.name if company else "—", alt=True)
    kv_row("Country", company.country if company else "—", "", "", alt=False)
    spacer()

    section_header("Plan & Period")
    kv_row("Plan", plan_name, "Billing Period", billing_period, alt=False)
    kv_row(
        "Period Start",
        fmt_date(sub.start_date) if sub and sub.start_date else "—",
        "Period End",
        fmt_date(sub.end_date) if sub and sub.end_date else "—",
        alt=True,
    )
    spacer()

    total_row(
        "Total Amount",
        fmt_currency(commission.subscription_amount, commission.currency),
    )
    spacer()

    section_header("Commission")
    kv_row(
        "Consultant",
        commission.consultant.email if commission.consultant else "—",
        "Rate",
        f"{commission.rate_percent:.0f}%",
        alt=False,
    )
    kv_row(
        "Consultant Share",
        fmt_currency(commission.commission_amount, commission.currency),
        "Admin Share",
        fmt_currency(commission.admin_share, commission.currency),
        alt=True,
    )
    kv_row(
        "Commission Status",
        commission.status.upper(),
        "Paid At",
        fmt_date(commission.paid_at) if commission.paid_at else "—",
        alt=False,
    )

    if invoice and invoice.fx_rate is not None:
        spacer()
        section_header("FX")
        kv_row(
            "Source Amount",
            fmt_currency(invoice.fx_source_amount, invoice.fx_source_currency),
            "Rate",
            f"1 {invoice.fx_source_currency or ''} = {invoice.fx_rate:.4f} {commission.currency or ''}".strip(),
            alt=False,
        )

    # ---- Serialize ----
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_POST
def commission_mark_paid(request, commission_id):
    """Admin records that they've actually disbursed a pending commission."""
    if not request.user.is_superuser:
        raise PermissionDenied()
    commission = get_object_or_404(ConsultantCommission, id=commission_id)
    if commission.status != "pending":
        messages.warning(request, "This commission is not in pending state.")
        return redirect("commissions")
    commission.status = "paid"
    commission.paid_at = timezone.now()
    commission.save(update_fields=["status", "paid_at", "updated_at"])
    messages.success(request, f"Commission for {commission.consultant.email} marked as paid.")
    return redirect("commissions")


def _maybe_create_commission(sub, now):
    plan_code = (sub.plan.code or "").lower() if sub.plan_id else ""
    if plan_code in ("", "free"):
        return

    business_user = sub.user
    primary_company = getattr(business_user, "primary_company", None)
    if not primary_company or not primary_company.consultant_id:
        return

    consultant = primary_company.consultant
    invoice = Invoice.objects.filter(subscription=sub).order_by("-created_at").first()
    if not invoice:
        return

    rate = Decimal("10.00")
    commission_amount = (invoice.amount * rate / Decimal("100")).quantize(Decimal("0.01"))

    ConsultantCommission.objects.get_or_create(
        consultant=consultant,
        subscription=sub,
        defaults={
            "business_user": business_user,
            "company": primary_company,
            "invoice": invoice,
            "subscription_amount": invoice.amount,
            "currency": invoice.currency,
            "rate_percent": rate,
            "commission_amount": commission_amount,
            "status": "pending",
        },
    )


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
