import re

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import Tenant, Company, UserCompany
from accounts.constants import CompanyClassificationChoices, CountryChoices
from billing.utils import get_user_plan, get_active_subscription

# First / last name: 1-50 chars, letters (incl. accented) + spaces/hyphens/apostrophes/periods.
NAME_RE = re.compile(r"^[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ\s'\-.]{0,49}$")
COUNTRY_CODES = {code for code, _ in CountryChoices.CHOICES}

# 2-100 chars, letters (incl. accented) / digits / spaces / & ' . , - ( ) only, must contain at least one letter.
COMPANY_NAME_RE = re.compile(r"^(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}$")

# Domain: 4-253 chars, ASCII labels separated by dots, TLD of 2+ letters (e.g. mycompany.com).
DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$",
    re.IGNORECASE,
)

# Website URL (strict): http/https only, valid domain + TLD, optional port, URL-safe path/query.
WEBSITE_URL_RE = re.compile(
    r"^https?://"
    r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)*"
    r"\.[a-z]{2,}"
    r"(?::\d{1,5})?"
    r"(?:/[A-Za-z0-9\-._~/]*)?"
    r"(?:\?[A-Za-z0-9\-._~&=]*)?"
    r"/?$",
    re.IGNORECASE,
)

# Phone: 7-25 chars, digits plus + - ( ) and spaces.
PHONE_CHARSET_RE = re.compile(r"^[\d+\-\s()]{7,25}$")

# City and Country: letters, spaces, hyphens, apostrophes (plus periods for city).
CITY_NAME_RE = re.compile(r"^[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s'\-.]{1,59}$")
COUNTRY_NAME_RE = re.compile(r"^[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s'\-]{1,59}$")


@login_required
def profile_view(request):
    user = request.user
    user_company = user.primary_company

    if request.method == "POST":
        form_type = request.POST.get("form_type", "")

        # ---- Edit personal profile (available to all users / all plans) ----
        if form_type == "edit_profile":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            country = request.POST.get("country", "").strip().upper()

            if not first_name or not NAME_RE.match(first_name):
                messages.error(request, "Enter a valid first name (letters, spaces, hyphens, apostrophes; up to 50 characters).")
                return redirect("profile")
            if not last_name or not NAME_RE.match(last_name):
                messages.error(request, "Enter a valid last name (letters, spaces, hyphens, apostrophes; up to 50 characters).")
                return redirect("profile")

            if phone:
                if not PHONE_CHARSET_RE.match(phone):
                    messages.error(request, "Phone may only contain digits and the symbols + - ( ) and spaces (7-25 characters).")
                    return redirect("profile")
                digits = re.sub(r"\D", "", phone)
                if not (5 <= len(digits) <= 15):
                    messages.error(request, "Phone must contain 5-15 digits.")
                    return redirect("profile")

            if country and country not in COUNTRY_CODES:
                messages.error(request, "Please select a valid country from the list.")
                return redirect("profile")

            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone or None
            user.country = country or None
            user.save(update_fields=["first_name", "last_name", "phone", "country", "updated_at"])

            messages.success(request, "Profile updated successfully.")
            return redirect("profile")

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

        if not COMPANY_NAME_RE.match(company_name):
            messages.error(
                request,
                "Company name must be 2-100 characters and may only contain letters, digits, spaces, and the symbols & ' . , - ( ).",
            )
            return redirect("profile")

        if Company.objects.filter(name__iexact=company_name).exists():
            messages.error(request, "A company with this name already exists. Please choose a different name.")
            return redirect("profile")

        if not domain:
            messages.error(request, "Domain is required.")
            return redirect("profile")

        domain = domain.lower()
        if not DOMAIN_RE.match(domain):
            messages.error(
                request,
                "Enter a valid domain like mycompany.com (4-253 characters, letters/digits/hyphens separated by dots, with a TLD of at least 2 letters).",
            )
            return redirect("profile")

        # Check if domain already exists (case-insensitive)
        if Tenant.objects.filter(domain__iexact=domain).exists():
            messages.error(request, "This domain is already taken.")
            return redirect("profile")

        if website and not WEBSITE_URL_RE.match(website):
            messages.error(
                request,
                "Enter a valid website URL like https://example.com (only letters, digits, and - . _ / in the path).",
            )
            return redirect("profile")

        if phone:
            if not PHONE_CHARSET_RE.match(phone):
                messages.error(
                    request,
                    "Phone may only contain digits and the symbols + - ( ) and spaces (7-25 characters).",
                )
                return redirect("profile")
            digits = re.sub(r"\D", "", phone)
            if not (5 <= len(digits) <= 15):
                messages.error(request, "Phone must contain 5-15 digits.")
                return redirect("profile")

        if city and not CITY_NAME_RE.match(city):
            messages.error(
                request,
                "City may only contain letters, spaces, hyphens, apostrophes and periods (2-60 characters).",
            )
            return redirect("profile")

        if country and not COUNTRY_NAME_RE.match(country):
            messages.error(
                request,
                "Country may only contain letters, spaces, hyphens and apostrophes (2-60 characters).",
            )
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
        "countries": CountryChoices.CHOICES,
        "user_plan": get_user_plan(user),
        "subscription": get_active_subscription(user),
    }
    return render(request, "profile/profile.html", context)
