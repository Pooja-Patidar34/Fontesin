from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import Tenant, Company, UserCompany
from accounts.constants import CompanyClassificationChoices
from billing.utils import get_user_plan, get_active_subscription


@login_required
def profile_view(request):
    user = request.user
    user_company = user.primary_company

    if request.method == "POST":
        # Company creation from profile
        company_name = request.POST.get("company_name", "").strip()
        domain = request.POST.get("domain", "").strip()
        classification = request.POST.get("classification", "")
        website = request.POST.get("website", "").strip()
        phone = request.POST.get("company_phone", "").strip()
        city = request.POST.get("city", "").strip()
        country = request.POST.get("company_country", "").strip()

        if not company_name:
            messages.error(request, "Company name is required.")
            return redirect("profile")

        if not domain:
            messages.error(request, "Domain is required.")
            return redirect("profile")

        # Check if domain already exists
        if Tenant.objects.filter(domain=domain).exists():
            messages.error(request, "This domain is already taken.")
            return redirect("profile")

        # Create tenant internally
        tenant = Tenant.objects.create(
            name=company_name,
            domain=domain,
        )

        # Create company linked to the new tenant
        company = Company.objects.create(
            tenant=tenant,
            name=company_name,
            classification=classification or None,
            website=website or None,
            phone=phone or None,
            city=city or None,
            country=country or None,
            owner_user=user,
        )

        # Link user to the new tenant and company
        user.tenant = tenant
        user.primary_company = company
        user.save()

        UserCompany.objects.get_or_create(
            user=user,
            company=company,
            defaults={"is_primary": True},
        )

        messages.success(request, "Company created successfully!")
        return redirect("profile")

    context = {
        "active_menu": "profile",
        "user_company": user_company,
        "classifications": CompanyClassificationChoices.CHOICES,
        "user_plan": get_user_plan(user),
        "subscription": get_active_subscription(user),
    }
    return render(request, "profile/profile.html", context)
