import json
import random
from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages

from billing.models import CommercialPlan, Subscription, Invoice


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
    plans = CommercialPlan.objects.filter(is_active=True)

    comparison_rows = [
        {"label": "World Map Access", "key": "world_map"},
        {"label": "Country Profiles / Day", "key": "country_profiles"},
        {"label": "Company Registry Data", "key": "company_registry"},
        {"label": "Advanced Analytics", "key": "advanced_analytics"},
        {"label": "Data Export (CSV/Excel/PDF)", "key": "data_export"},
        {"label": "API Access", "key": "api_access"},
        {"label": "Multilicense", "key": "multilicense"},
        {"label": "Select Country / Region", "key": "select_country_region"},
        {"label": "Franchise Management", "key": "franchise_management"},
        {"label": "Multi-Currency Billing", "key": "multi_currency"},
        {"label": "Dedicated Account Manager", "key": "dedicated_manager"},
        {"label": "Pro Forma Invoice", "key": "pro_forma_invoice"},
        {"label": "Support Level", "key": "support"},
    ]

    plans_json = json.dumps({
        p.code: {"name": p.name, "price": float(p.price), "label": f"{p.name} Plan — ${p.price:,.0f}/year"}
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

    plan_code = request.POST.get("plan_code")
    plan = CommercialPlan.objects.filter(code=plan_code, is_active=True).first()

    if not plan:
        messages.error(request, "Invalid plan selected")
        return redirect("membership")

    user = request.user

    # Cancel any existing active subscription
    Subscription.objects.filter(
        user=user,
        status__in=["active", "trial", "created"]
    ).update(status="cancelled")

    now = timezone.now()
    end_date = now + timedelta(days=365)

    # Create subscription
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        status="active" if plan.code == "free" else "created",
        start_date=now,
        end_date=end_date,
    )

    # Update user subscription_plan field
    user.subscription_plan = plan.code
    user.save(update_fields=["subscription_plan"])

    # Create invoice
    year = now.strftime("%Y")
    seq = random.randint(100000, 999999)
    invoice_number = f"FONTESIN-{plan.code.upper()}-{year}{seq}"
    variable_symbol = f"{year}{seq}"
    specific_symbol = year
    payment_reference = f"FONTESIN-{plan.code.upper()}-{variable_symbol}"

    invoice = Invoice.objects.create(
        subscription=subscription,
        invoice_number=invoice_number,
        amount=plan.price,
        currency=plan.currency,
        status="paid" if plan.code == "free" else "pending",
        variable_symbol=variable_symbol,
        specific_symbol=specific_symbol,
        payment_reference=payment_reference,
        due_date=now + timedelta(days=14),
    )

    return redirect("invoice_detail", invoice_id=invoice.id)


@login_required
def invoice_detail(request, invoice_id):
    invoice = Invoice.objects.select_related(
        "subscription__plan", "subscription__user"
    ).filter(id=invoice_id, subscription__user=request.user).first()

    if not invoice:
        messages.error(request, "Invoice not found")
        return redirect("membership")

    return render(request, "website/invoice.html", {"invoice": invoice})