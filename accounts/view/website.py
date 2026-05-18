import json
import random
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages

from billing.models import CommercialPlan, Subscription, Invoice, ConsultantCommission


def home(request):
    return render(request, 'website/index.html')

def about(request):
    return render(request, 'website/about.html')

def worldmap(request):
    from billing.utils import get_user_plan, get_plan_feature
    plan = get_user_plan(request.user) if request.user.is_authenticated else None
    world_map_access = get_plan_feature(request.user, "world_map") if request.user.is_authenticated else "Basic"
    return render(request, 'website/worldmap.html', {
        "plan": plan,
        "world_map_access": world_map_access,
    })

def career(request):
    return render(request, 'website/career.html')

def contact(request):
    return render(request, 'website/contact.html')


def membership(request):
    # Don't gate the page itself — users on Free/Basic/Pro need to be able
    # to view plans in order to upgrade. The actual create-subscription
    # decision (same-tier? pending already? unknown plan?) lives in
    # `select_plan` so this view stays a pure read-only catalogue.
    if request.user.is_authenticated:
        pending_sub = (
            Subscription.objects
            .filter(user=request.user, status="created")
            .select_related("plan")
            .first()
        )
        if pending_sub:
            messages.info(
                request,
                f"Your upgrade to the {pending_sub.plan.name} plan is pending admin approval. "
                "You can't start another upgrade until that one is approved or rejected.",
            )

        # If the user has been auto-moved from a now-deactivated paid plan
        # to Free, surface that on the membership page so the "pick a new
        # plan" CTA carries the right framing.
        from billing.utils import get_deactivated_paid_plan
        deactivated_plan = get_deactivated_paid_plan(request.user)
        if deactivated_plan:
            messages.warning(
                request,
                f"Your {deactivated_plan.name} plan was deactivated by the admin. "
                "You have been moved to the Free plan. "
                "Please activate another plan from the options below.",
            )

    plans = CommercialPlan.objects.filter(is_active=True)

    comparison_rows = [
        {"label": "Profile Visibility", "key": "profile_visibility"},
        {"label": "Geographic Access Scope", "key": "geographic_scope"},
        {"label": "Search Scope", "key": "search_scope"},
        {"label": "Company Certification", "key": "company_certification"},
        {"label": "Partnerships", "key": "partnerships"},
        {"label": "Messaging", "key": "messaging"},
        {"label": "Saving Databases", "key": "saving_databases"},
    ]

    plans_json = json.dumps({
        p.code: {
            "name": p.name,
            "price": float(p.price),
            "billing_period": p.billing_period,
            "label": f"{p.name} Plan — ${p.price:,.0f}/{'month' if p.billing_period == 'monthly' else 'year'}",
        }
        for p in plans
    })

    return render(request, 'website/membership.html', {
        "plans": plans,
        "comparison_rows": comparison_rows,
        "plans_json": plans_json,
    })


@login_required
def select_plan(request):
    if request.method != "POST":
        return redirect("membership")

    user = request.user

    # Block stacking: one pending upgrade at a time.
    pending_sub = (
        Subscription.objects
        .filter(user=user, status="created")
        .select_related("plan")
        .first()
    )
    if pending_sub:
        messages.info(
            request,
            f"Your upgrade to the {pending_sub.plan.name} plan is already pending admin approval.",
        )
        return redirect("dashboard")

    plan_code = request.POST.get("plan_code")
    plan = CommercialPlan.objects.filter(code=plan_code, is_active=True).first()

    if not plan:
        messages.error(request, "Invalid plan selected")
        return redirect("membership")

    # Tier check: only allow strictly-higher-tier moves. This is the actual
    # "upgrade" guard — same plan or a downgrade is a no-op (or worse, would
    # silently issue a refund-shaped flow we don't support yet).
    from billing.utils import PLAN_TIERS
    current_active = (
        Subscription.objects
        .filter(user=user, status="active")
        .select_related("plan")
        .first()
    )
    if current_active:
        current_tier = PLAN_TIERS.get((current_active.plan.code or "").lower(), -1)
        new_tier = PLAN_TIERS.get((plan.code or "").lower(), -1)
        if new_tier <= current_tier:
            messages.info(
                request,
                f"You're already on the {current_active.plan.name} plan. Pick a higher tier to upgrade.",
            )
            return redirect("membership")

    now = timezone.now()
    if plan.billing_period == "monthly":
        end_date = now + relativedelta(months=1)
    else:
        end_date = now + relativedelta(years=1)

    # Free plan needs no admin approval — activate immediately.
    subscription_status = "active" if plan.code == "free" else "created"

    # If the user is buying a paid plan and doesn't have any active sub yet
    # (e.g. fresh signup straight to a paid tier), spin up a Free active sub
    # alongside the pending paid sub. This is what lets the user log into the
    # dashboard with Free-tier access while the paid upgrade is awaiting
    # admin approval — without it, they'd land back on /membership/ on next
    # login because there's no `status="active"` row to gate them through.
    if subscription_status == "created":
        has_active = Subscription.objects.filter(user=user, status="active").exists()
        if not has_active:
            free_plan = (
                CommercialPlan.objects
                .filter(code="free", is_active=True)
                .first()
            )
            if free_plan:
                Subscription.objects.create(
                    user=user,
                    plan=free_plan,
                    billing_period=free_plan.billing_period,
                    status="active",
                    start_date=now,
                    end_date=now + relativedelta(years=1),
                )
                user.subscription_plan = "free"
                user.save(update_fields=["subscription_plan"])

    # Create the requested subscription (free → active immediately, paid → created).
    # Snapshot `billing_period` from the plan at creation time — this is what
    # the bug fix is about: if the admin later edits the plan's billing_period
    # (yearly → monthly), this user's existing subscription must continue to
    # display and renew on its *original* cadence, not the plan's new one.
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        billing_period=plan.billing_period,
        status=subscription_status,
        start_date=now,
        end_date=end_date,
    )

    # Only sync User.subscription_plan when *this* sub is active now (free path).
    # For paid upgrades the sub starts as "created" — deferring the write keeps
    # User.subscription_plan in step with the actually-live plan until the admin
    # approves and `payment_approve` flips it.
    if subscription_status == "active":
        user.subscription_plan = plan.code
        user.save(update_fields=["subscription_plan"])

    # Create invoice
    year = now.strftime("%Y")
    seq = random.randint(100000, 999999)
    invoice_number = f"FONTESIN-{plan.code.upper()}-{year}{seq}"
    variable_symbol = f"{year}{seq}"
    specific_symbol = year
    payment_reference = f"FONTESIN-{plan.code.upper()}-{variable_symbol}"

    # ── Bank profile snapshot ──
    bank = _bank_details_for_user(user)
    bank_snapshot = dict(bank)  # shallow copy so future edits to dict literal don't mutate

    # ── FX freeze (only EU users on USD plans) ──
    invoice_amount = plan.price
    invoice_currency = (plan.currency or "USD").upper()
    fx_source_currency = ""
    fx_source_amount = None
    fx_rate = None
    user_country = (getattr(user, "country", "") or "").strip().upper()
    if user_country in _EUROPE_COUNTRY_CODES and invoice_currency == "USD":
        from billing.fx import convert, get_rate
        fx_source_currency = "USD"
        fx_source_amount = plan.price
        fx_rate = get_rate("USD", "EUR")
        invoice_amount = convert(plan.price, "USD", "EUR")
        invoice_currency = "EUR"

    # ── Sender (customer) snapshot ──
    address_parts = [
        getattr(user, "address_line1", None),
        getattr(user, "address_line2", None),
        getattr(user, "city", None),
        getattr(user, "state_region", None),
        getattr(user, "postal_code", None),
        getattr(user, "country", None),
    ]
    full_address = ", ".join([p for p in address_parts if p])

    full_phone = (getattr(user, "phone", "") or "").strip()
    if getattr(user, "national_prefix", None):
        full_phone = f"+{user.national_prefix} {full_phone}".strip()

    sender_snapshot = {
        "name": f"{user.first_name} {user.last_name}".strip(),
        "email": user.email,
        "phone": full_phone,
        "country": user_country or "",
        "address_line1": getattr(user, "address_line1", None) or "",
        "address_line2": getattr(user, "address_line2", None) or "",
        "city": getattr(user, "city", None) or "",
        "state_region": getattr(user, "state_region", None) or "",
        "postal_code": getattr(user, "postal_code", None) or "",
        "full_address": full_address,
        "tenant_name": user.tenant.name if getattr(user, "tenant", None) else "",
    }

    invoice = Invoice.objects.create(
        subscription=subscription,
        invoice_number=invoice_number,
        amount=invoice_amount,
        currency=invoice_currency,
        status="paid" if plan.code == "free" else "pending",
        variable_symbol=variable_symbol,
        specific_symbol=specific_symbol,
        payment_reference=payment_reference,
        due_date=now + timedelta(days=14),
        bank_snapshot=bank_snapshot,
        sender_snapshot=sender_snapshot,
        fx_source_currency=fx_source_currency,
        fx_source_amount=fx_source_amount,
        fx_rate=fx_rate,
    )

    return redirect("invoice_detail", invoice_id=invoice.id)


_EUROPE_COUNTRY_CODES = {"DE", "CZ", "GB", "FR", "NL", "PL", "AT", "CH", "SE"}

# Mercury bank account details per wire profile.
# Source: FONTES INC Mercury wire details (2026).
_BANK_DOMESTIC_US = {
    "profile": "domestic_us",
    "currency": "USD",
    "bank_name": "Choice Financial Group",
    "bank_address": "4501 23rd Avenue S, Fargo, ND 58104, USA",
    "aba_routing": "091311229",
    "swift": None,
    "account_label": "Account Number",
    "account_number": "202541415155",
    "account_kind": "Checking",
    "beneficiary_name": "FONTES INC",
    "beneficiary_address": "World Trade Center, Suite 8500, 85th floor, New York, NY 10007, USA",
    "remittance_reference": None,
}
_BANK_INTERNATIONAL_USD = {
    "profile": "international_usd",
    "currency": "USD",
    "bank_name": "Choice Financial Group",
    "bank_address": "4501 23rd Avenue S, Fargo, ND 58104, USA",
    "aba_routing": "091311229",
    "swift": "CHFGUS44021",
    "account_label": "IBAN / Account Number",
    "account_number": "202541415155",
    "account_kind": None,
    "beneficiary_name": "FONTES INC",
    "beneficiary_address": "World Trade Center, Suite 8500, 85th floor, New York, NY 10007, USA",
    "remittance_reference": None,
}
_BANK_INTERNATIONAL_EUR = {
    "profile": "international_eur",
    "currency": "EUR",
    "bank_name": "JP Morgan Chase Bank, N.A. – New York",
    "bank_address": "383 Madison Avenue, Floor 23, New York, NY 10017, USA",
    "aba_routing": "021000021",
    "swift": "CHASUS33XXX",
    "account_label": "IBAN / Account Number",
    "account_number": "707567692",
    "account_kind": None,
    "beneficiary_name": "Choice Financial Group",
    "beneficiary_address": "4501 23rd Ave S, Fargo, ND 58104, USA",
    "remittance_reference": "/FFC/202541415155/FONTES INC/New York, USA",
}


def _bank_details_for_user(user):
    """Return Mercury bank details dict for the user's region.
    US        → domestic US (USD)
    Europe    → international FX (EUR)
    Otherwise → international USD"""
    code = (getattr(user, "country", "") or "").strip().upper()
    if code == "US":
        return _BANK_DOMESTIC_US
    if code in _EUROPE_COUNTRY_CODES:
        return _BANK_INTERNATIONAL_EUR
    return _BANK_INTERNATIONAL_USD


@login_required
def invoice_detail(request, invoice_id):
    invoice = Invoice.objects.select_related(
        "subscription__plan", "subscription__user"
    ).filter(id=invoice_id).first()

    if not invoice:
        messages.error(request, "Invoice not found")
        return redirect("membership")

    # Access control: the subscription owner (business user) always sees their
    # own invoice. Superusers see everything. Consultants see an invoice when
    # they have a commission row tied to it (i.e. they earned on this sale).
    subscription_user = invoice.subscription.user if invoice.subscription_id else None
    is_owner = subscription_user is not None and subscription_user == request.user
    is_linked_consultant = ConsultantCommission.objects.filter(
        invoice=invoice, consultant=request.user
    ).exists()
    if not (request.user.is_superuser or is_owner or is_linked_consultant):
        messages.error(request, "Invoice not found")
        return redirect("membership")

    # The bank-details fallback should reflect the subscriber's region, not
    # the viewer's — an admin or consultant opening someone else's invoice
    # must see the same bank block the business user would.
    bank_user = subscription_user or request.user

    # Prefer the snapshot stored at invoice creation time. Fall back to a
    # live computation for legacy invoices that were created before snapshots
    # were introduced.
    bank = invoice.bank_snapshot or _bank_details_for_user(bank_user)
    sender = invoice.sender_snapshot

    invoice_currency = (invoice.currency or "USD").upper()

    # FX disclosure: if the invoice has a frozen rate, show that. Otherwise
    # do a live conversion against the bank's currency (legacy behavior).
    if invoice.fx_rate is not None:
        display_amount = invoice.amount
        display_currency = invoice_currency
        fx_rate = invoice.fx_rate
        fx_source_currency = invoice.fx_source_currency or None
        fx_source_amount = invoice.fx_source_amount
    else:
        from billing.fx import convert, get_rate
        target_currency = bank.get("currency", invoice_currency).upper()
        if invoice_currency != target_currency:
            display_amount = convert(invoice.amount, invoice_currency, target_currency)
            fx_rate = get_rate(invoice_currency, target_currency)
            fx_source_currency = invoice_currency
            fx_source_amount = invoice.amount
            display_currency = target_currency
        else:
            display_amount = invoice.amount
            display_currency = invoice_currency
            fx_rate = None
            fx_source_currency = None
            fx_source_amount = None

    return render(request, "website/invoice.html", {
        "invoice": invoice,
        "bank": bank,
        "sender": sender,
        "display_amount": display_amount,
        "display_currency": display_currency,
        "fx_rate": fx_rate,
        "fx_source_currency": fx_source_currency,
        "fx_source_amount": fx_source_amount,
    })