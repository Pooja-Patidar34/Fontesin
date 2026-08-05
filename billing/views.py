import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import IntegrityError, transaction
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
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from billing.models import Invoice, Subscription, CommercialPlan, ConsultantCommission
from billing.plan_i18n import attach_plan_display_fields, localized_plan_name

_SUBSCRIPTION_STATUS_CODES = {code for code, _ in Subscription.STATUS_CHOICES}


def _safe_next_or_default(request, default_name):
    """Return the form-supplied `next` URL when it's a same-host relative
    redirect target, otherwise the named-URL default.

    The Payments page injects `?page=N&status=Y` into a hidden `next` field
    so approve/reject/edit can bounce the admin back to whatever pagination
    page (and filter tab) they were on — without this, every action snaps
    the list back to page 1 and they lose their place. We validate against
    open-redirect by requiring the URL is in-host.
    """
    target = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if target and url_has_allowed_host_and_scheme(
        url=target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(target)
    return redirect(default_name)

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
        .select_related("user", "plan", "company", "company__certified_by")
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
        messages.warning(request, _("This subscription is not pending approval."))
        return _safe_next_or_default(request, "payments")

    now = timezone.now()

    # Supersede any other still-active subscription ON THE SAME COMPANY (e.g.
    # the Free plan the company was on before this upgrade). Plans are
    # company-scoped, so this must be scoped to sub.company — cancelling every
    # active sub for the user would wrongly kill the plans on their OTHER
    # companies. Without it the company ends up with two `active` rows and
    # `get_active_subscription` picks one with `.first()` and no ordering — a
    # non-deterministic plan tier. Legacy rows without a company fall back to
    # the old per-user supersede. Using "cancelled" because the existing
    # STATUS_CHOICES has no "superseded"/"expired" — closest fit.
    # Supersede + activate is one unit of work: the old subscription is already
    # cancelled by the time this row is saved, so a failure in between (a DB
    # error, or maybe_create_commission_for_subscription raising) would leave
    # the company with NO active plan. Same guarantee select_plan gives its
    # downgrade-to-Free path.
    with transaction.atomic():
        supersede_qs = Subscription.objects.filter(status="active").exclude(pk=sub.pk)
        if sub.company_id:
            supersede_qs = supersede_qs.filter(company_id=sub.company_id)
        else:
            supersede_qs = supersede_qs.filter(user=sub.user, company__isnull=True)
        supersede_qs.update(status="cancelled", end_date=now, updated_at=now)

        # Recompute end_date from the approval moment so the user gets the full
        # paid period starting NOW, not from when they originally submitted.
        # Previously select_plan set end_date at submission time (start + 1y for
        # yearly / +1m for monthly), so any days the request sat in the admin
        # queue silently shortened the subscription — a yearly Pro approved 11
        # days late ended ~11 months later, not 12. Driving end_date off the
        # billing_period at approval time fixes that drift.
        #
        # We read the period off `sub.billing_period` (a per-subscription
        # snapshot taken at purchase time), not off `sub.plan.billing_period` —
        # that way, if the admin edits the plan template between submission and
        # approval (yearly → monthly), the user still gets the period they
        # actually bought.
        from dateutil.relativedelta import relativedelta
        sub.status = "active"
        sub.start_date = now
        if sub.billing_period == "monthly":
            sub.end_date = now + relativedelta(months=1)
        else:
            sub.end_date = now + relativedelta(years=1)
        sub.save(update_fields=["status", "start_date", "end_date", "updated_at"])

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
        maybe_create_commission_for_subscription(sub, now)

    messages.success(request, _("Subscription for %(email)s has been approved.") % {"email": sub.user.email})
    return _safe_next_or_default(request, "payments")


@login_required
def commission_list(request):
    """Earnings page. Consultants see only their own rows; superusers see all
    rows across the platform (for payout review)."""
    # Consultants and Micro-Franchise owners (who also earn plan commissions —
    # spec §9.1.2) see their own rows; superusers see everything.
    from accounts.utils.permissions import can_certify_companies, is_suspended_micro_owner
    if not can_certify_companies(request.user):
        # A suspended Micro owner keeps the tab but is shown a "suspended" message.
        if is_suspended_micro_owner(request.user):
            from django.utils.translation import gettext as _
            return render(request, "dashboard/franchise_suspended.html", {"feature": _("Commissions")})
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

    ctx = {
        "commissions": page_obj,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "active_menu": "commissions",
        "totals_by_currency": totals_by_currency,
        "pending_by_currency": pending_by_currency,
        "admin_totals_by_currency": admin_totals_by_currency,
        "viewing_as_admin": request.user.is_superuser,
    }
    # AJAX tab / pagination switch → return only the panel partial so the
    # caller can swap #commissions-panel in place without reloading the
    # whole dashboard chrome.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "dashboard/_commissions_panel.html", ctx)
    return render(request, "dashboard/commissions.html", ctx)


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
    ws.title = _("Invoice")

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

    plan_name = localized_plan_name(sub.plan) if sub and sub.plan else "—"
    billing_period = (
        _("Monthly") if sub and sub.billing_period == "monthly"
        else _("Annual") if sub else "—"
    )
    sub_user_name = (
        f"{business_user.first_name} {business_user.last_name}".strip()
        if business_user else "—"
    )
    sub_user_role = (
        business_user.role.name if business_user and business_user.role else "—"
    )

    # ---- Build the workbook ----
    title_banner(_("FONTESIN  ·  Invoice %(number)s") % {"number": inv_number}, height=36)
    spacer()

    section_header(_("Invoice"))
    kv_row(
        _("Invoice Number"), inv_number, _("Status"),
        (invoice.status if invoice else "—").upper(), alt=False,
    )
    kv_row(
        _("Issue Date"),
        fmt_date(invoice.created_at) if invoice else "—",
        _("Paid At"),
        fmt_date(invoice.paid_at) if invoice and invoice.paid_at else "—",
        alt=True,
    )
    if invoice and invoice.status != "paid" and invoice.due_date:
        kv_row(_("Due Date"), fmt_date(invoice.due_date), "", "", alt=False)
    spacer()

    section_header(_("Subscriber"))
    kv_row(_("Name"), sub_user_name, _("Email"), business_user.email if business_user else "—", alt=False)
    kv_row(_("Role"), sub_user_role, _("Company"), company.name if company else "—", alt=True)
    kv_row(_("Country"), company.country if company else "—", "", "", alt=False)
    spacer()

    section_header(_("Plan & Period"))
    kv_row(_("Plan"), plan_name, _("Billing Period"), billing_period, alt=False)
    kv_row(
        _("Period Start"),
        fmt_date(sub.start_date) if sub and sub.start_date else "—",
        _("Period End"),
        fmt_date(sub.end_date) if sub and sub.end_date else "—",
        alt=True,
    )
    spacer()

    total_row(
        _("Total Amount"),
        fmt_currency(commission.subscription_amount, commission.currency),
    )
    spacer()

    section_header(_("Commission"))
    kv_row(
        _("Consultant"),
        commission.consultant.email if commission.consultant else "—",
        _("Rate"),
        f"{commission.rate_percent:.0f}%",
        alt=False,
    )
    kv_row(
        _("Consultant Share"),
        fmt_currency(commission.commission_amount, commission.currency),
        _("Admin Share"),
        fmt_currency(commission.admin_share, commission.currency),
        alt=True,
    )
    kv_row(
        _("Commission Status"),
        commission.status.upper(),
        _("Paid At"),
        fmt_date(commission.paid_at) if commission.paid_at else "—",
        alt=False,
    )

    if invoice and invoice.fx_rate is not None:
        spacer()
        section_header(_("FX"))
        kv_row(
            _("Source Amount"),
            fmt_currency(invoice.fx_source_amount, invoice.fx_source_currency),
            _("Rate"),
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
        messages.warning(request, _("This commission is not in pending state."))
        return redirect("commissions")
    commission.status = "paid"
    commission.paid_at = timezone.now()
    commission.save(update_fields=["status", "paid_at", "updated_at"])

    # Now that it's PAID, send the "earned" notification to the consultant and
    # every superuser (the pending notification went out at creation time).
    try:
        from accounts.utils.notifications import notify_commission_earned
        notify_commission_earned(commission)
    except Exception:
        pass

    messages.success(request, _("Commission for %(email)s marked as paid.") % {"email": commission.consultant.email})
    return redirect("commissions")


def _commission_company_for_subscription(user, sub):
    """The company whose certifying consultant earns the commission for this
    plan (`sub`): the FIRST CERTIFIED company the user created during this plan's
    window — from when this plan was initiated up to when the NEXT paid plan was
    initiated. Falls back to the latest certified company the user had before
    this plan (carried over), else the primary company.              

    Why the window is keyed on the subscription's `created_at` (when the plan
    was requested) and the NEXT subscription's `created_at`, NOT `start_date`:
    payment_approve RESETS `start_date` to the approval moment, which is often
    AFTER the new company was created (user requests the upgrade, creates the
    company, admin approves later). Keying on `start_date` would then exclude the
    new company and wrongly fall back to the old/primary one — which is exactly
    why the commission kept showing the old company name. Using the stable
    request-time boundaries fixes that.

    "First in window" (not latest) is deliberate: a SECOND/additional company
    created under the same plan is later than the plan's first company, so it
    doesn't change the attribution — matching "additional company, same plan =>
    no change".
    """
    from accounts.models import Company

    lower = getattr(sub, "created_at", None)
    # When the user's NEXT paid plan was initiated — caps this plan's window so
    # each plan claims only companies created during its own tenure.
    next_sub = (
        Subscription.objects
        .filter(user=user, created_at__gt=sub.created_at)
        .exclude(plan__code__iexact="free")
        .order_by("created_at")
        .first()
    ) if lower else None

    # NOTE: this window query is intentionally NOT filtered by certification
    # status. The plan's company is "the first company created during the plan",
    # certified or not. If it's still pending, maybe_create_commission_for_subscription
    # holds the commission (its "must be certified" gate) — so NO commission
    # shows until the consultant certifies it, instead of prematurely falling
    # back to a previously-certified company.
    qs = Company.objects.filter(owner_user=user)
    if lower:
        qs = qs.filter(created_at__gte=lower)
    if next_sub:
        qs = qs.filter(created_at__lt=next_sub.created_at)
    first_in_window = qs.order_by("created_at").first()
    if first_in_window:
        return first_in_window

    # No company created during this plan's window at all → carry over the
    # latest certified company from before the plan, else the primary company.
    #
    # BUT a company that ALREADY backs a commission for another (earlier) plan
    # must never be reused — otherwise the same company pays the consultant a
    # second time on the next plan (e.g. BU upgrades Basic -> Pro WITHOUT
    # creating a new company: the Basic company would wrongly generate a Pro
    # commission too). If every carry-over candidate is already commissioned,
    # this plan gets NO commission (return None) — which is correct, because no
    # new company was created during this plan's tenure.
    used_company_ids = set(
        ConsultantCommission.objects
        .filter(business_user=user, status__in=["pending", "paid"])
        .exclude(subscription=sub)
        .values_list("company_id", flat=True)
    )
    if lower:
        prior = (
            Company.objects
            .filter(
                owner_user=user,
                certification_status__iexact="certified",
                created_at__lt=lower,
            )
            .exclude(id__in=used_company_ids)
            .order_by("-created_at")
            .first()
        )
        if prior:
            return prior
    primary = getattr(user, "primary_company", None)
    if primary and primary.id in used_company_ids:
        return None
    return primary


def maybe_create_commission_for_subscription(sub, now):
    """Create the consultant-commission row for `sub` if all conditions are met.

    Idempotent via the (consultant, subscription) unique constraint, so safe
    to call from both payment_approve (the live approval path) AND from a
    backfill path that runs when the user belatedly certifies / links a company.

    Eligibility rule: plans are company-scoped, so each PLAN's commission goes
    to the consultant who CERTIFIED the subscription's OWN company. The company
    must be certified and its `certified_by` must be a consultant — a business
    user creates a company, a consultant certifies it, that company's owner buys
    a plan for it, and the certifying consultant earns 10% when the plan is
    approved. Renewals repeat this on each new approved subscription.

    Legacy subscriptions with no company attached fall back to the historical
    "first company created during the plan window" heuristic
    (`_commission_company_for_subscription`).
    """
    plan_code = (sub.plan.code or "").lower() if sub.plan_id else ""
    if plan_code in ("", "free"):
        return

    business_user = sub.user
    if not business_user:
        return

    # The plan's own company (company-scoped subscriptions). Fall back to the
    # legacy window heuristic only for subscriptions predating the company link.
    company = sub.company if getattr(sub, "company_id", None) else None
    if company is None:
        company = _commission_company_for_subscription(business_user, sub)
    if not company:
        return

    # Pay the consultant who CERTIFIED that company. Only certified companies
    # with a certifying consultant pay out.
    if (company.certification_status or "").lower() != "certified":
        return
    consultant = company.certified_by
    if not consultant:
        return
    # The certifier earns the commission. This is a Standard Consultant or a
    # Micro-Franchise owner (a consultant-level franchise — spec §9.1.2 "sell
    # user plans", §11). A superadmin override certification doesn't generate a
    # payout, so check the two earning roles explicitly rather than via
    # can_certify_companies (which also allows superusers).
    from accounts.utils.permissions import is_micro_franchise_owner
    consultant_role = (
        (consultant.role.code or "").lower() if getattr(consultant, "role", None) else ""
    )
    if consultant_role != "consultant" and not is_micro_franchise_owner(consultant):
        return

    invoice = Invoice.objects.filter(subscription=sub).order_by("-created_at").first()
    if not invoice:
        return

    rate = Decimal("10.00")
    commission_amount = (invoice.amount * rate / Decimal("100")).quantize(Decimal("0.01"))

    # Reconcile this subscription's commission so the row reflects the CURRENT
    # certifier + company for this plan. This matters when the plan is approved
    # BEFORE the plan's company is certified: the commission first gets created
    # against a fallback (the primary company / its certifier), then once the
    # right company is certified we must fix it — including reassigning to a
    # DIFFERENT consultant if that consultant certified the new company.
    #
    #   - Correct consultant already has the row → just fix a stale company name.
    #   - Otherwise → delete any PENDING fallback row left on this subscription
    #     for a different consultant, then create the correct one.
    #   - PAID rows are never touched (a disbursed commission isn't revoked).
    correct = ConsultantCommission.objects.filter(
        subscription=sub, consultant=consultant
    ).first()
    company_corrected = False
    if correct:
        created = False
        commission = correct
        if commission.company_id != company.id:
            commission.company = company
            commission.business_user = business_user
            commission.save(update_fields=["company", "business_user", "updated_at"])
            company_corrected = True
    else:
        ConsultantCommission.objects.filter(
            subscription=sub, status="pending"
        ).exclude(consultant=consultant).delete()
        commission = ConsultantCommission.objects.create(
            consultant=consultant,
            subscription=sub,
            business_user=business_user,
            company=company,
            invoice=invoice,
            subscription_amount=invoice.amount,
            currency=invoice.currency,
            rate_percent=rate,
            commission_amount=commission_amount,
            status="pending",
        )
        created = True

    # Notify the consultant + every superuser that a commission is PENDING — on
    # a brand-new commission, and also when an existing one's company was
    # corrected (so the Notifications tab reflects the right company name). The
    # "earned" notification is sent later, when the super admin marks it PAID
    # (see commission_mark_paid). Reassignments to a different consultant come
    # through the `created` branch (new row), so the correct consultant is
    # notified there. Wrapped so a notification hiccup never breaks the flow.
    if created or company_corrected:
        try:
            from accounts.utils.notifications import notify_commission_pending
            notify_commission_pending(commission)
        except Exception:
            pass


# Back-compat alias for internal callers — keep the old underscore name
# working until every reference is migrated.
_maybe_create_commission = maybe_create_commission_for_subscription


def backfill_consultant_commissions_for_user(user, now=None):
    """Walk every approved paid subscription the user holds and (re)try
    commission creation.

    Called at the moment a user gains a consultant linkage on their primary
    company — either by joining an existing consultant-routed company or
    by creating one that gets auto-routed. Subs in status 'created'
    (pending admin approval) are intentionally skipped here: their
    commission will be generated by payment_approve once it sees the now-
    present primary_company.consultant_id.
    """
    if not user or not getattr(user, "primary_company_id", None):
        return 0
    company = user.primary_company
    if not company or not company.consultant_id:
        return 0

    when = now or timezone.now()
    created = 0
    eligible_subs = (
        Subscription.objects
        .filter(user=user, status__in=["active", "trial"])
        .exclude(plan__code__iexact="free")
        .select_related("plan")
    )
    for sub in eligible_subs:
        before = ConsultantCommission.objects.filter(
            consultant_id=company.consultant_id, subscription=sub
        ).count()
        maybe_create_commission_for_subscription(sub, when)
        after = ConsultantCommission.objects.filter(
            consultant_id=company.consultant_id, subscription=sub
        ).count()
        if after > before:
            created += 1
    return created


@login_required
@require_POST
def payment_reject(request, subscription_id):
    if not request.user.is_superuser:
        raise PermissionDenied()

    sub = get_object_or_404(Subscription, id=subscription_id)

    if sub.status != "created":
        messages.warning(request, _("This subscription is not pending approval."))
        return _safe_next_or_default(request, "payments")

    sub.status = "cancelled"
    sub.save(update_fields=["status", "updated_at"])

    # Mark the related invoice as failed
    Invoice.objects.filter(subscription=sub, status="pending").update(status="failed")

    messages.success(request, _("Subscription for %(email)s has been rejected.") % {"email": sub.user.email})
    return _safe_next_or_default(request, "payments")


@login_required
def payment_detail_ajax(request, subscription_id):
    """Return subscription data as JSON for the edit modal."""
    if not request.user.is_superuser:
        return JsonResponse({"error": _("forbidden")}, status=403)

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

    # Validate the end date BEFORE applying any change, so a bad date aborts
    # the whole edit cleanly (no half-written plan/status). The end date may
    # not be moved into the past. We still allow re-submitting an already-past
    # date unchanged — that happens when an admin edits the plan/status of an
    # expired subscription without touching the date — but never let them set
    # a NEW past date.
    new_end_dt = None
    if end_date:
        try:
            new_end_dt = timezone.make_aware(datetime.strptime(end_date, "%Y-%m-%d"))
        except ValueError:
            messages.error(request, _("Invalid end date."))
            return _safe_next_or_default(request, "payments")

        current_end_date = sub.end_date.date() if sub.end_date else None
        if new_end_dt.date() < timezone.localdate() and new_end_dt.date() != current_end_date:
            messages.error(
                request,
                _("End date cannot be in the past. Choose today or a future date."),
            )
            return _safe_next_or_default(request, "payments")

    plan_changed = False
    if plan_id:
        plan = get_object_or_404(CommercialPlan, id=plan_id, is_active=True)
        plan_changed = sub.plan_id != plan.id
        sub.plan = plan
        if sub.user:
            sub.user.subscription_plan = plan.code
            sub.user.save(update_fields=["subscription_plan"])

    # Status flip, supersede, invoice/commission realignment and the sub.save()
    # are one unit of work: the previous plan is cancelled before this row is
    # written, so a failure in between would leave the company with no active
    # plan. Mirrors payment_approve.
    with transaction.atomic():
        if status and status in _SUBSCRIPTION_STATUS_CODES:
            old_status = sub.status
            sub.status = status
            # If changing to active, supersede any OTHER active subscription for
            # this user first, then mark the invoice paid. The DB enforces
            # unique_active_subscription_per_user, so without superseding (e.g. the
            # Free plan they're currently on, or a previously-approved sub) flipping
            # this row to "active" raises an IntegrityError — exactly what happened
            # approving a cancelled subscription. Mirrors payment_approve.
            if status == "active" and old_status != "active":
                now = timezone.now()
                # Scope the supersede to the subscription's COMPANY — plans are
                # company-scoped (unique_active_subscription_per_company), so
                # cancelling every active sub for the user would wrongly kill the
                # plans on their other companies. Legacy rows without a company fall
                # back to the old per-user supersede.
                supersede_qs = Subscription.objects.filter(status="active").exclude(pk=sub.pk)
                if sub.company_id:
                    supersede_qs = supersede_qs.filter(company_id=sub.company_id)
                else:
                    supersede_qs = supersede_qs.filter(user=sub.user, company__isnull=True)
                supersede_qs.update(status="cancelled", end_date=now, updated_at=now)
                Invoice.objects.filter(subscription=sub, status="pending").update(
                    status="paid", paid_at=now
                )
                # Sync the user's current plan to the now-active plan.
                if sub.user and sub.plan_id:
                    new_code = (sub.plan.code or "").lower()
                    if new_code and sub.user.subscription_plan != new_code:
                        sub.user.subscription_plan = new_code
                        sub.user.save(update_fields=["subscription_plan"])

        if new_end_dt is not None:
            sub.end_date = new_end_dt

        sub.save()

        # If the plan changed, realign the unpaid invoice and any PENDING commission
        # to the NEW plan's price. Without this, downgrading (e.g. Global -> Basic)
        # leaves the commission at the old plan's rate, because the commission amount
        # was copied from the original invoice and is never recomputed otherwise.
        # Paid invoices/commissions are left untouched as historical records.
        if plan_changed:
            new_price = sub.plan.price
            new_currency = (getattr(sub.plan, "currency", None) or "USD").upper()
            Invoice.objects.filter(subscription=sub).exclude(status="paid").update(
                amount=new_price, currency=new_currency
            )
            for comm in ConsultantCommission.objects.filter(subscription=sub, status="pending"):
                comm.subscription_amount = new_price
                comm.currency = new_currency
                comm.commission_amount = (
                    new_price * comm.rate_percent / Decimal("100")
                ).quantize(Decimal("0.01"))
                comm.save(update_fields=[
                    "subscription_amount", "currency",
                    "commission_amount", "updated_at",
                ])

    messages.success(request, _("Subscription for %(email)s updated successfully.") % {"email": sub.user.email})
    return _safe_next_or_default(request, "payments")


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

    for plan in page_obj:
        attach_plan_display_fields(plan)

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

        moved_count = 0
        # When a *paid* plan is switched off, anyone currently subscribed to
        # it loses paid access. We cancel those active/trial subs and move
        # each user back to the always-on Free tier, so they keep working
        # with reduced privileges instead of being silently broken. The Free
        # plan itself is never toggled this way — `subscriptions.html` only
        # exposes the toggle for paid plans — but we still skip the move
        # logic for "free" defensively.
        if not plan.is_active and (plan.code or "").lower() != "free":
            moved_count = _move_subscribers_to_free(plan)

        status_label = _("activated") if plan.is_active else _("deactivated")
        msg = _("Plan '%(name)s' has been %(status)s.") % {
            "name": plan.name,
            "status": status_label,
        }
        if moved_count:
            msg += " " + (
                _("%(count)s active subscriber(s) moved to the Free plan.")
                % {"count": moved_count}
            )

        if is_ajax:
            return JsonResponse({
                "ok": True,
                "is_active": plan.is_active,
                "message": msg,
                "moved_count": moved_count,
            })

        messages.success(request, msg)
    except Exception as e:
        logger.error("Error toggling plan %s: %s", plan_id, e)
        if is_ajax:
            return JsonResponse({"ok": False, "message": _("Failed to update plan status.")}, status=500)
        messages.error(request, _("Failed to update plan status."))

    return redirect("subscriptions")


def _move_subscribers_to_free(deactivated_plan):
    """Cancel every active/trial subscription on `deactivated_plan` and put
    each affected user on the Free plan. Returns the number of users moved.

    The cancelled rows are left in place (status="cancelled", end_date=now)
    so the user-side plan card can detect the auto-move and show
    "your <plan> was deactivated by the admin" until they pick a new plan.
    """
    now = timezone.now()
    free_plan = CommercialPlan.objects.filter(code="free").first()
    if free_plan is None:
        logger.warning(
            "plan_toggle: deactivated plan %s but no Free plan exists — "
            "subscribers left orphaned.", deactivated_plan.code,
        )
        return 0

    affected = list(
        Subscription.objects
        .filter(plan=deactivated_plan, status__in=["active", "trial"])
        .select_related("user")
    )
    moved = 0
    for sub in affected:
        user = sub.user
        if user is None:
            continue

        # One atomic block PER SUBSCRIBER, not per batch. The cancel frees the
        # unique-active constraint slot that the Free insert then claims, so the
        # two must commit together: without this, a failing insert (a genuine
        # race on unique_active_subscription_per_company) would leave that
        # subscriber cancelled with no plan at all. Catching per iteration also
        # keeps one bad row from aborting the batch and skipping everyone after
        # it — the remaining subscribers still get moved.
        try:
            with transaction.atomic():
                # Cancel the now-invalid paid sub. This frees the per-company
                # active constraint slot so we can insert the Free replacement
                # on the next line. Plans are company-scoped, so the Free
                # replacement is created for the subscription's COMPANY (not
                # just the user).
                sub.status = "cancelled"
                sub.end_date = now
                sub.save(update_fields=["status", "end_date", "updated_at"])

                # Idempotent guard: skip the Free insert if this company (or the
                # user, for legacy company-less subs) already has an active sub.
                active_filter = (
                    {"company_id": sub.company_id}
                    if sub.company_id
                    else {"user": user, "company__isnull": True}
                )
                has_active = Subscription.objects.filter(
                    status__in=["active", "trial"], **active_filter
                ).exists()
                if not has_active:
                    from dateutil.relativedelta import relativedelta
                    Subscription.objects.create(
                        user=user,
                        company_id=sub.company_id,
                        plan=free_plan,
                        billing_period=free_plan.billing_period,
                        status="active",
                        start_date=now,
                        end_date=now + relativedelta(years=1),
                    )

                if user.subscription_plan != "free":
                    user.subscription_plan = "free"
                    user.save(update_fields=["subscription_plan"])
        except IntegrityError:
            # This subscriber keeps their original paid row (the cancel rolled
            # back), so they're no worse off than before the toggle. Logged so
            # the admin can be told the count moved is short.
            logger.exception(
                "plan_toggle: could not move subscription %s (user %s) to Free",
                sub.pk, getattr(user, "pk", None),
            )
            continue

        moved += 1
    return moved


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
        messages.success(request, _("Plan '%(name)s' updated successfully.") % {"name": plan.name})

    except (ValueError, TypeError) as e:
        logger.exception("Invalid data editing plan %s: %s", plan_id, e)
        messages.error(request, _("Invalid data provided. Please check your input."))
    except Exception as e:
        logger.exception("Error editing plan %s: %s", plan_id, e)
        messages.error(request, _("Failed to update plan."))

    return redirect("subscriptions")
