import re

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from accounts.models import Tenant, Company, UserCompany
from accounts.constants import (
    CompanyClassificationChoices,
    CountryChoices,
    COUNTRY_STATES,
)

CLASSIFICATION_CODES = {code for code, _ in CompanyClassificationChoices.CHOICES}
COUNTRY_LABELS = dict(CountryChoices.CHOICES)
from billing.utils import get_user_plan, get_active_subscription, get_pending_subscription


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"

# First / last name: 2-50 chars, letters (incl. accented) + spaces/hyphens/apostrophes/periods.
NAME_RE = re.compile(r"^[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ\s'\-.]{1,49}$")
COUNTRY_CODES = {code for code, _ in CountryChoices.CHOICES}

# 2-100 chars, letters (incl. accented) / digits / spaces / & ' . , - ( ) only, must contain at least one letter.
COMPANY_NAME_RE = re.compile(r"^(?=.*[A-Za-z\u00C0-\u024F])[A-Za-z\u00C0-\u024F0-9&'.,\-()\s]{2,100}$")

# Company registration ID: 2-100 chars, letters/digits and - / . _ only.
REGISTRATION_ID_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9\-/._]{2,100}$")

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
STATE_NAME_RE = COUNTRY_NAME_RE

# Address line: letters/digits/spaces and the explicit allowlist , . - / #; 3-120 chars.
ADDRESS_LINE_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z\u00C0-\u024F0-9\s,./#\-]{3,120}$")

# Postal code: alphanumerics with optional spaces/hyphens (US/UK/CA/etc.); 3-12 chars.
POSTAL_CODE_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-z0-9\s\-]{3,12}$")


@login_required
def company_search_ajax(request):
    """Type-ahead search for the 'Join existing company' picker on the profile
    page. Limited to 20 hits, name LIKE — server-side so the dropdown scales
    past a small directory."""
    q = (request.GET.get("q") or "").strip()
    qs = Company.objects.filter(is_active=True)
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("name").values("id", "name", "city", "country", "classification")[:20]

    results = [
        {
            "id": str(row["id"]),
            "name": row["name"],
            "city": row["city"] or "",
            "country": row["country"] or "",
            "classification": row["classification"] or "",
        }
        for row in qs
    ]
    return JsonResponse({"results": results})


@login_required
def profile_view(request):
    user = request.user
    user_company = user.primary_company

    if request.method == "POST":
        form_type = request.POST.get("form_type", "")

        # ---- Join an existing company (alternative to creating one) ----
        if form_type == "join_company":
            if user_company is not None:
                messages.warning(request, "You are already linked to a company.")
                return redirect("profile")

            company_id = (request.POST.get("company_id") or "").strip()
            if not company_id:
                messages.error(request, "Please select a company to join.")
                return redirect("profile")

            company = Company.objects.filter(id=company_id, is_active=True).first()
            if not company:
                messages.error(request, "That company is unavailable. Please pick another.")
                return redirect("profile")

            user.primary_company = company
            if company.tenant_id:
                user.tenant = company.tenant
            user.save(update_fields=["primary_company", "tenant", "updated_at"])

            UserCompany.objects.get_or_create(
                user=user,
                company=company,
                defaults={"is_primary": True},
            )

            messages.success(request, f"You're now linked to {company.name}.")
            return redirect("profile")

        # ---- Edit personal profile (available to all users / all plans) ----
        if form_type == "edit_profile":
            ajax = _is_ajax(request)

            def _fail(msg):
                if ajax:
                    return JsonResponse({"ok": False, "message": msg}, status=400)
                messages.error(request, msg)
                return redirect("profile")

            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            phone = request.POST.get("phone", "").strip()
            country = request.POST.get("country", "").strip().upper()

            if not first_name or not NAME_RE.match(first_name):
                return _fail("Enter a valid first name (2-50 characters; letters, spaces, hyphens, apostrophes).")
            if not last_name or not NAME_RE.match(last_name):
                return _fail("Enter a valid last name (2-50 characters; letters, spaces, hyphens, apostrophes).")

            if phone:
                if not PHONE_CHARSET_RE.match(phone):
                    return _fail("Phone may only contain digits and the symbols + - ( ) and spaces (7-25 characters).")
                digits = re.sub(r"\D", "", phone)
                if not (5 <= len(digits) <= 15):
                    return _fail("Phone must contain 5-15 digits.")

            if country and country not in COUNTRY_CODES:
                return _fail("Please select a valid country from the list.")

            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone or None
            user.country = country or None
            user.save(update_fields=["first_name", "last_name", "phone", "country", "updated_at"])

            if ajax:
                return JsonResponse({
                    "ok": True,
                    "message": "Profile updated successfully.",
                    "user": {
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": user.phone or "",
                        "country": user.country or "",
                    },
                })

            messages.success(request, "Profile updated successfully.")
            return redirect("profile")

        # Company creation from profile.
        # Collapse runs of whitespace in the company name so "Acme  Corp" and
        # "Acme Corp" can't sneak past the uniqueness check by virtue of an
        # extra space.
        company_name = re.sub(r"\s+", " ", request.POST.get("company_name", "").strip())
        registration_id = request.POST.get("registration_id", "").strip()
        domain = request.POST.get("domain", "").strip()
        classification = request.POST.get("classification", "").strip()
        website = request.POST.get("website", "").strip()
        phone = request.POST.get("company_phone", "").strip()
        phone_secondary = request.POST.get("phone_secondary", "").strip()
        fax = request.POST.get("fax", "").strip()
        address_line1 = request.POST.get("address_line1", "").strip()
        address_line2 = request.POST.get("address_line2", "").strip()
        city = request.POST.get("city", "").strip()
        state = request.POST.get("state", "").strip()
        postal_code = request.POST.get("postal_code", "").strip()
        country = request.POST.get("company_country", "").strip()

        # Stash the cleaned values so a validation-failure redirect can
        # repopulate the form on the next GET — losing every field on a
        # single duplicate-domain (or any other) error is hostile UX. The
        # session entry is consumed and removed by the GET branch below.
        request.session["create_company_form"] = {
            "company_name": company_name,
            "registration_id": registration_id,
            "domain": domain,
            "classification": classification,
            "website": website,
            "company_phone": phone,
            "phone_secondary": phone_secondary,
            "fax": fax,
            "address_line1": address_line1,
            "address_line2": address_line2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "company_country": country,
        }

        if not company_name:
            messages.error(request, "Company name is required.")
            return redirect("profile")

        if not COMPANY_NAME_RE.match(company_name):
            messages.error(
                request,
                "Company name must be 2-100 characters and may only contain letters, digits, spaces, and the symbols & ' . , - ( ).",
            )
            return redirect("profile")

        # Strict same-name guard: reject if either an active Company OR an
        # active Tenant with this name already exists. Profile creation
        # provisions a Tenant alongside the Company, and Tenant.name is
        # unique=True at the DB level — without the Tenant half of this
        # check, a tenant-only collision later raises IntegrityError and
        # the user sees a 500 instead of "already exists".
        if (
            Company.objects.filter(name__iexact=company_name).exists()
            or Tenant.objects.filter(name__iexact=company_name).exists()
        ):
            messages.error(
                request,
                "A company with this name already exists. Please choose a different name.",
            )
            return redirect("profile")

        if not registration_id:
            messages.error(request, "Registration No. is required.")
            return redirect("profile")

        if not REGISTRATION_ID_RE.match(registration_id):
            messages.error(
                request,
                "Registration No. may only contain letters, digits, and the symbols - / . _ (2-100 characters).",
            )
            return redirect("profile")

        if Company.objects.filter(registration_id__iexact=registration_id).exists():
            messages.error(
                request,
                "A company with this Registration No. already exists. Registration No. must be unique.",
            )
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

        if not classification:
            messages.error(request, "Classification is required.")
            return redirect("profile")

        if classification not in CLASSIFICATION_CODES:
            messages.error(request, "Please select a valid classification from the list.")
            return redirect("profile")

        if website and not WEBSITE_URL_RE.match(website):
            messages.error(
                request,
                "Enter a valid website URL like https://example.com (only letters, digits, and - . _ / in the path).",
            )
            return redirect("profile")

        def _validate_phone_like(value, label):
            if not PHONE_CHARSET_RE.match(value):
                return f"{label} may only contain digits and the symbols + - ( ) and spaces (7-25 characters)."
            digits = re.sub(r"\D", "", value)
            if not (5 <= len(digits) <= 15):
                return f"{label} must contain 5-15 digits."
            return None

        if phone:
            err = _validate_phone_like(phone, "Phone")
            if err:
                messages.error(request, err)
                return redirect("profile")

        if phone_secondary:
            err = _validate_phone_like(phone_secondary, "Secondary phone")
            if err:
                messages.error(request, err)
                return redirect("profile")

        if fax:
            err = _validate_phone_like(fax, "Fax")
            if err:
                messages.error(request, err)
                return redirect("profile")

        if address_line1 and not ADDRESS_LINE_RE.match(address_line1):
            messages.error(
                request,
                "Address line 1 may only contain letters, digits, spaces and the symbols , . - / # (3-120 characters).",
            )
            return redirect("profile")

        if address_line2 and not ADDRESS_LINE_RE.match(address_line2):
            messages.error(
                request,
                "Address line 2 may only contain letters, digits, spaces and the symbols , . - / # (3-120 characters).",
            )
            return redirect("profile")

        if not city:
            messages.error(request, "City is required.")
            return redirect("profile")

        if not CITY_NAME_RE.match(city):
            messages.error(
                request,
                "City may only contain letters, spaces, hyphens, apostrophes and periods (2-60 characters).",
            )
            return redirect("profile")

        # Country comes from the dropdown as an ISO-3166 alpha-2 code (e.g. "US").
        # State must be one of the known subdivisions for that country — both
        # selects are populated from the same map the server uses, so the only
        # way to get a value outside the map is a tampered request.
        if not country:
            messages.error(request, "Country is required.")
            return redirect("profile")

        country_code = country.upper()
        if country_code not in COUNTRY_LABELS:
            messages.error(request, "Please select a valid country from the list.")
            return redirect("profile")
        country = country_code

        valid_states = COUNTRY_STATES.get(country_code, [])
        if not state:
            messages.error(request, "State is required.")
            return redirect("profile")

        if valid_states and state not in valid_states:
            messages.error(
                request,
                "Please select a valid state for the chosen country.",
            )
            return redirect("profile")

        if postal_code and not POSTAL_CODE_RE.match(postal_code):
            messages.error(
                request,
                "Postal code may only contain letters, digits, spaces and hyphens (3-12 characters).",
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
            registration_id=registration_id,
            classification=classification or None,
            website=website or None,
            phone=phone or None,
            phone_secondary=phone_secondary or None,
            fax=fax or None,
            address_line1=address_line1 or None,
            address_line2=address_line2 or None,
            city=city or None,
            state=state or None,
            postal_code=postal_code or None,
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

        request.session.pop("create_company_form", None)
        messages.success(request, "Company created successfully!")
        return redirect("profile")

    context = {
        "active_menu": "profile",
        "user_company": user_company,
        "classifications": CompanyClassificationChoices.CHOICES,
        "countries": CountryChoices.CHOICES,
        "country_states": COUNTRY_STATES,
        "user_plan": get_user_plan(user),
        "subscription": get_active_subscription(user),
        "pending_subscription": get_pending_subscription(user),
        # Pop-and-render: the previous POST stashed cleaned values here on a
        # validation-failure redirect; consuming them now means a manual page
        # refresh starts with a blank form again.
        "create_company_form": request.session.pop("create_company_form", None),
    }
    return render(request, "profile/profile.html", context)
