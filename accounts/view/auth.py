import logging
import re
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import UserRole, Permission
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse
from accounts.models import Tenant, Company, Role, UserCompany, User, DueDiligence
from django.db import IntegrityError
from accounts.constants import CountryChoices, LanguageChoices
import random
from datetime import date, timedelta
from django.utils import timezone
from accounts.models import User, PasswordResetToken
from accounts.utils.mailer import send_otp_email

logger = logging.getLogger("technical")

# def admin_login(request):
#     if request.user.is_authenticated:
#         return redirect("dashboard")

#     if request.method == "POST":
#         email = request.POST.get("email")
#         password = request.POST.get("password")

#         user = authenticate(request, email=email, password=password)

#         if user is None:
#             messages.error(request, "Invalid credentials")
#             return render(request, "auth/login.html")

#         if not user.is_active:
#             messages.error(request, "Your account is inactive")
#             return render(request, "auth/login.html")

#         if user.is_superuser:
#             login(request, user)
#             return redirect("dashboard")

#         try:
#             user_role = UserRole.objects.select_related("role").get(user=user)
#             if user_role.role.name == "tenant_admin":
#                 login(request, user)
#                 return redirect("dashboard")
#         except UserRole.DoesNotExist:
#             pass

#         messages.error(
#             request,
#             "You are not allowed to access the admin panel"
#         )

#     return render(request, "auth/login.html")



def admin_login(request):
    if request.user.is_authenticated:
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("dashboard")

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "auth/login.html")

        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
            messages.error(request, "Enter a valid email address.")
            return render(request, "auth/login.html")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "auth/login.html")

        user = authenticate(request, email=email, password=password)

        if user is None:
            # Django's ModelBackend rejects inactive users at authenticate(), so
            # distinguish "deactivated by admin" from "wrong credentials" here.
            # Only reveal deactivation when the password actually matches — this
            # avoids leaking which emails are registered.
            candidate = User.objects.filter(email__iexact=email).first()
            if candidate and not candidate.is_active and candidate.check_password(password):
                messages.error(
                    request,
                    "Your account has been deactivated by admin. Please contact support.",
                )
            else:
                messages.error(request, "Invalid credentials")
            return render(request, "auth/login.html")

        login(request, user)

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        if user.is_superuser or (user.role and user.role.name == "tenant_admin"):
            return redirect("dashboard")

        # Non-subscribing roles: go straight to the dashboard (no membership flow).
        non_subscribing = {"consultant", "coordinator", "franchise"}
        role_code = (user.role.code or "").lower() if user.role else ""
        if role_code in non_subscribing:
            return redirect("dashboard")

        # Subscription status for business users.
        # A pending paid sub no longer blocks login — users get into the
        # dashboard with their current active (Free) plan and the pending
        # upgrade is surfaced as a "Pending" status on their profile until
        # the admin approves. Only redirect to membership if the user has
        # no active sub at all (and no pending one — select_plan now
        # auto-creates a Free active sub for paid signups so this branch
        # only fires for users who haven't visited membership yet).
        from billing.models import Subscription
        active_sub = Subscription.objects.filter(user=user, status="active").first()
        if active_sub:
            return redirect("dashboard")

        pending_sub = Subscription.objects.filter(user=user, status="created").first()
        if pending_sub:
            return redirect("dashboard")

        return redirect("membership")

    return render(request, "auth/login.html")


def admin_logout(request):
    logout(request)
    return redirect("login")


def check_email_exists(request):
    """
    Lightweight AJAX endpoint used by the multi-step register form to validate
    the email field on phase 1, before letting the user advance to phase 2.

    Returns: {"exists": bool}
    """
    email = (request.GET.get("email") or "").strip()
    if not email:
        return JsonResponse({"exists": False})
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({"exists": exists})


def register_view(request):

    companies = Company.objects.filter(is_active=True)
    ctx = {
        "companies": companies,
        "country_choices": CountryChoices.CHOICES,
        "language_choices": LanguageChoices.CHOICES,
    }

    if request.method == "POST":

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        country = request.POST.get("country", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        role_name = request.POST.get("role", "").strip()
        company_id = request.POST.get("company_id", "").strip()

        # required fields validation
        required_fields = {
            "First name": first_name,
            "Last name": last_name,
            "Email": email,
            "Phone": phone,
            "Country": country,
            "Password": password,
            "Role": role_name,
        }
        missing = [name for name, value in required_fields.items() if not value]
        if missing:
            messages.error(request, f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required.")
            return render(request, "auth/register.html", ctx)

        # emoji detection
        emoji_pattern = re.compile(
            r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
            r"\U0001F1E0-\U0001F1FF\U00002600-\U000026FF\U00002700-\U000027BF"
            r"\U0001F900-\U0001F9FF\U0000200D\U000020E3\U000FE00F]"
        )

        # name validation (letters, accented chars, spaces, hyphens, apostrophes — no digits, no emojis)
        name_regex = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ\s'\-]+$")

        if emoji_pattern.search(first_name) or not name_regex.match(first_name):
            messages.error(request, "First name must contain only letters. Digits and emojis are not allowed.")
            return render(request, "auth/register.html", ctx)
        if emoji_pattern.search(last_name) or not name_regex.match(last_name):
            messages.error(request, "Last name must contain only letters. Digits and emojis are not allowed.")
            return render(request, "auth/register.html", ctx)

        # email format validation (stricter)
        email_regex = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
        if not email_regex.match(email):
            messages.error(request, "Enter a valid email address (e.g. john@company.com).")
            return render(request, "auth/register.html", ctx)

        # phone validation per country
        PHONE_RULES = {
            "US": (10, 10), "CA": (10, 10), "GB": (10, 10),
            "DE": (10, 11), "FR": (9, 9), "NL": (9, 9),
            "PL": (9, 9), "AT": (10, 11), "CH": (9, 9),
            "SE": (9, 10), "CZ": (9, 9), "AE": (9, 9),
            "SG": (8, 8), "AU": (9, 9), "JP": (10, 10),
            "BR": (10, 11), "IN": (10, 10), "MX": (10, 10),
            "KR": (10, 11),
        }
        # strip country code prefix if present
        phone_digits = re.sub(r"[^\d]", "", phone.lstrip("+"))
        # if phone starts with country code, strip it
        phone_clean = re.sub(r"[\s\-()]", "", phone)
        if phone_clean.startswith("+"):
            # remove the + and country code digits, keep local number
            phone_digits = re.sub(r"[^\d]", "", phone)
            # strip leading country code by using the raw local digits
            parts = phone.strip().split(" ", 1)
            if len(parts) == 2:
                phone_digits = re.sub(r"[^\d]", "", parts[1])

        min_len, max_len = PHONE_RULES.get(country, (7, 15))
        if not phone_digits.isdigit() or len(phone_digits) < min_len or len(phone_digits) > max_len:
            messages.error(request, f"Phone number must be {min_len}-{max_len} digits for the selected country.")
            return render(request, "auth/register.html", ctx)

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/register.html", ctx)

        # email exists check (case-insensitive — create_user lowercases the domain
        # via normalize_email, so a case-sensitive lookup misses existing rows
        # and the INSERT then trips the unique constraint)
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email already exists")
            return render(request, "auth/register.html", ctx)

        # password match check
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "auth/register.html", ctx)

        tenant, _ = Tenant.objects.get_or_create(name="Default")

        role = Role.objects.filter(code__iexact=role_name).first()

        if not role:
            messages.error(request, "Invalid role selected")
            return render(request, "auth/register.html", ctx)

        # create user — guard against the race between the iexact check above
        # and the INSERT (two concurrent submits, or normalize_email collapsing
        # to an existing row)
        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                tenant=tenant,
                role=role,
                phone=phone,
                country=country,
                # Identity verification has not happened yet — the account
                # stays gated on the /verify/ step (see
                # RequireIdentityVerificationMiddleware) and cannot reach plan
                # selection or the dashboard until Veriff returns "approved".
                verification_status="pending",
            )
        except IntegrityError:
            messages.error(request, "Email already exists")
            return render(request, "auth/register.html", ctx)

        # Business users register without a company — they create or join one
        # from their profile after sign-up. Consultants, coordinators, and
        # franchise partners now follow the same pattern: they register the
        # company they represent from /profile/ after the application step.
        # Any company_id POSTed by these roles is ignored as a safety net
        # (the HTML form no longer sends one — see toggleOthersOption()).
        if role_name in ("business_user", "consultant", "coordinator", "franchise"):
            company_id = ""

        # link company (other roles only — none today, kept for future roles)
        if company_id:
            company = Company.objects.filter(id=company_id).first()
            if company:
                user.primary_company = company
                user.save()

                UserCompany.objects.create(
                    user=user,
                    company=company,
                    is_primary=True
                )

        # Notify consultants in the new user's region, in parallel with the
        # existing super-admin notification flow, and surface the details the
        # user just filled in. Scoped to business-user signups — those are the
        # prospective clients a regional consultant would follow up with;
        # consultants/coordinators/franchises aren't leads for other
        # consultants. Wrapped so a notification hiccup never breaks sign-up.
        if role_name == "business_user":
            try:
                from accounts.utils.notifications import notify_consultants_new_user
                notify_consultants_new_user(
                    user,
                    language=request.POST.get("language", "").strip(),
                    interest=request.POST.get("interest", "").strip(),
                )
            except Exception:
                pass

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        # LOCAL TESTING ONLY: when VERIFF_BYPASS is on, skip the Veriff step
        # entirely — auto-approve the account and send it straight to the next
        # registration step (application form for consultant / coordinator /
        # franchise, otherwise plan selection). Off by default in production.
        if getattr(settings, "VERIFF_BYPASS", False):
            user.verification_status = "approved"
            user.save(update_fields=["verification_status"])
            if role_name in ("consultant", "coordinator", "franchise"):
                return redirect("apply")
            return redirect("membership")

        # All roles go through Veriff identity verification
        # After verification, consultant/coordinator/franchise → /apply/, others → /membership/
        return redirect("/verify/")

    return render(request, "auth/register.html", ctx)



@login_required
def identity_verification_view(request):
    user = request.user

    if not user.role or not user.role.code:
        messages.error(request, "Your account does not have a valid role assigned. Please contact support.")
        return redirect("login")

    role_code = user.role.code.lower()
    show_apply_link = role_code in ('consultant', 'coordinator', 'franchise')

    from FontEsin.middleware.require_verification import VERIFIED_STATUSES

    # A user landing here right after finishing Veriff often hasn't had their
    # decision webhook processed yet (it's async, and on local/IP-only hosts
    # Veriff can't call the webhook at all). Without this, they'd see the
    # "Start Verification" screen again even though they just passed. Pull the
    # decision straight from Veriff so a completed session is recognised on
    # return instead of waiting on the webhook.
    if (user.verification_status or "") not in VERIFIED_STATUSES:
        from accounts.view.veriff import sync_veriff_decision
        synced = sync_veriff_decision(user)
        if synced:
            user.refresh_from_db(fields=["verification_status"])

    # Already verified — there's nothing to do on this screen, so move the
    # user on to the next step in the registration flow (per the diagram:
    # SUCCESSFUL verification → application form for consultant / coordinator
    # / franchise, otherwise → plan selection). Without this an approved user
    # who navigates back to /verify/ would be stranded on the start screen.
    current_status = (user.verification_status or "")
    if current_status in VERIFIED_STATUSES:
        return redirect("apply" if show_apply_link else "membership")

    # The user has already started/finished a Veriff session but the decision
    # isn't "approved" yet (Veriff is still processing — its decision lags the
    # user clicking "Continue"). Show a "Verifying your identity…" screen that
    # polls /veriff/status/ and auto-forwards to plan selection the moment the
    # decision lands, instead of the "Start Verification" screen. Terminal
    # failures (declined / resubmission_requested / expired / abandoned) drop
    # back to the start screen so the user can re-attempt.
    FAILED_STATUSES = ("declined", "resubmission_requested", "expired", "abandoned")
    verification_in_progress = (
        bool((user.veriff_session_id or "").strip())
        and current_status not in FAILED_STATUSES
    )

    return render(
        request,
        "auth/verify.html",
        {
            "VERIFF_PUBLIC_KEY": settings.VERIFF_API_KEY,
            "show_apply_link": show_apply_link,
            "verification_in_progress": verification_in_progress,
            "verification_status": current_status,
        }
    )


@login_required
def apply_view(request):
    user = request.user

    if not user.role or not user.role.code:
        messages.error(request, "Your account does not have a valid role assigned. Please contact support.")
        return redirect("login")

    role_code = user.role.code.lower()
    if 'consultant' in role_code:
        role_value = 'consultant'
        role_label = 'Consultant'
        role_icon = '\U0001F4BC'
    elif 'coordinator' in role_code:
        role_value = 'coordinator'
        role_label = 'Coordinator'
        role_icon = '\U0001F30D'
    elif 'franchise' in role_code:
        role_value = 'franchise'
        role_label = 'Franchise Partner'
        role_icon = '\U0001F680'
    else:
        messages.error(request, "The application form is only available for consultants, coordinators, and franchise partners.")
        return redirect("dashboard")

    # Pre-fill the Company Information section from the company the user picked
    # at /register/ (primary_company). Fall back to any applied_* values already
    # saved on the user (e.g. if they reopen the form after a partial submit).
    pc = user.primary_company
    prefill = {
        "company_name": (pc.name if pc else "") or (user.applied_company_name or ""),
        "company_reg_number": (pc.registration_id if pc else "") or (user.applied_company_reg_number or ""),
        "country_of_incorporation": (pc.country if pc else "") or (user.applied_country_of_incorporation or ""),
        "legal_form": (pc.classification if pc else "") or (user.applied_legal_form or ""),
        "year_founded": user.applied_year_founded or "",
        "num_employees": user.applied_num_employees or "",
        "company_website": (pc.website if pc else "") or (user.applied_company_website or ""),
    }

    return render(request, "auth/apply.html", {
        "role_value": role_value,
        "role_label": role_label,
        "role_icon": role_icon,
        "prefill": prefill,
        "year_founded_min": 1800,
        "year_founded_max": date.today().year,
    })


@login_required
def apply_submit(request):
    if request.method != "POST":
        return redirect("apply")

    user = request.user

    if not user.role or not user.role.code:
        messages.error(request, "Your account does not have a valid role assigned. Please contact support.")
        return redirect("login")

    role_code = user.role.code.lower()
    if not any(r in role_code for r in ('consultant', 'coordinator', 'franchise')):
        messages.error(request, "The application form is only available for consultants, coordinators, and franchise partners.")
        return redirect("dashboard")

    # Collect and strip fields
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    birth_date = request.POST.get("birth_date", "").strip()
    nationality = request.POST.get("nationality", "").strip()
    phone = request.POST.get("phone", "").strip()
    linkedin_url = request.POST.get("linkedin_url", "").strip()
    address_line1 = request.POST.get("address_line1", "").strip()

    current_position = request.POST.get("current_position", "").strip()
    years_of_experience = request.POST.get("years_of_experience", "").strip()
    primary_industry = request.POST.get("primary_industry", "").strip()
    professional_summary = request.POST.get("professional_summary", "").strip()

    applied_company_name = request.POST.get("applied_company_name", "").strip()
    applied_company_reg_number = request.POST.get("applied_company_reg_number", "").strip()
    applied_country_of_incorporation = request.POST.get("applied_country_of_incorporation", "").strip()
    applied_legal_form = request.POST.get("applied_legal_form", "").strip()
    year_founded = request.POST.get("applied_year_founded", "").strip()
    applied_num_employees = request.POST.get("applied_num_employees", "").strip()
    applied_company_website = request.POST.get("applied_company_website", "").strip()

    target_region = request.POST.get("target_region", "").strip()
    franchise_type = request.POST.get("franchise_type", "").strip()
    motivation = request.POST.get("motivation", "").strip()
    network_connections = request.POST.get("network_connections", "").strip()
    expected_companies = request.POST.get("expected_companies", "").strip()
    reference_1 = request.POST.get("reference_1", "").strip()
    reference_2 = request.POST.get("reference_2", "").strip()

    # Validate required fields
    required_fields = {
        "First name": first_name,
        "Last name": last_name,
        "Date of birth": birth_date,
        "Nationality": nationality,
        "Phone": phone,
        "Address": address_line1,
        "Current position": current_position,
        "Years of experience": years_of_experience,
        "Primary industry": primary_industry,
        "Professional summary": professional_summary,
        "Motivation": motivation,
        # Company Information — these end up on the Company row created below
        # and become the user's primary_company. Name / Country / Legal Form
        # already have HTML `required`; the Registration Number was previously
        # optional but is now mandatory so the company is uniquely identifiable
        # and admins have something to verify on the certification request.
        "Company name": applied_company_name,
        "Company registration number": applied_company_reg_number,
        "Country of incorporation": applied_country_of_incorporation,
        "Legal form": applied_legal_form,
    }
    missing = [name for name, value in required_fields.items() if not value]
    if missing:
        messages.error(request, f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required.")
        return redirect("apply")

    # Validate phone length and characters (7-20 chars, digits/+/-/space/parentheses only)
    phone_digits = re.sub(r"\D", "", phone)
    if not re.fullmatch(r"[\d+\-\s()]{7,20}", phone) or not (7 <= len(phone_digits) <= 15):
        messages.error(request, "Phone number must be 7-15 digits (you may include +, spaces, dashes, or parentheses).")
        return redirect("apply")

    # Validate Year Founded if provided. Must be a 4-digit integer between
    # 1800 and the current year — without this guard, "13" or "20240" would
    # be saved verbatim because the int() cast below accepts both.
    applied_year_founded_int = None
    if year_founded:
        if not re.fullmatch(r"\d{4}", year_founded):
            messages.error(request, "Year Founded must be a 4-digit year (e.g. 2015).")
            return redirect("apply")
        yf = int(year_founded)
        current_year = date.today().year
        if yf < 1800 or yf > current_year:
            messages.error(
                request,
                f"Year Founded must be between 1800 and {current_year}.",
            )
            return redirect("apply")
        applied_year_founded_int = yf

    # Age must be consistent with selected years of experience (min working age 16)
    try:
        dob = date.fromisoformat(birth_date)
    except ValueError:
        messages.error(request, "Enter a valid date of birth.")
        return redirect("apply")

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    exp_match = re.match(r"^\s*(\d+)", years_of_experience)
    min_exp = int(exp_match.group(1)) if exp_match else 0
    required_age = 16 + min_exp
    if age < required_age:
        messages.error(
            request,
            f"Date of Birth and Years of Experience are inconsistent. Minimum age of {required_age} is expected for the selected experience level.",
        )
        return redirect("apply")

    # Validate declarations
    if not request.POST.get("declared_truthful"):
        messages.error(request, "You must declare that all information provided is truthful.")
        return redirect("apply")
    if not request.POST.get("accepted_terms"):
        messages.error(request, "You must accept the terms and conditions.")
        return redirect("apply")

    # Assign validated fields
    user.first_name = first_name
    user.last_name = last_name
    user.birth_date = birth_date or None
    user.nationality = nationality
    user.phone = phone
    user.linkedin_url = linkedin_url
    user.address_line1 = address_line1

    user.current_position = current_position
    user.years_of_experience = years_of_experience
    user.primary_industry = primary_industry
    user.professional_summary = professional_summary

    user.applied_company_name = applied_company_name
    user.applied_company_reg_number = applied_company_reg_number
    user.applied_country_of_incorporation = applied_country_of_incorporation
    user.applied_legal_form = applied_legal_form
    user.applied_year_founded = applied_year_founded_int
    user.applied_num_employees = applied_num_employees
    user.applied_company_website = applied_company_website

    user.target_region = target_region
    user.franchise_type = franchise_type
    user.motivation = motivation
    user.network_connections = network_connections
    user.expected_companies = expected_companies
    user.reference_1 = reference_1
    user.reference_2 = reference_2

    # Application status
    user.application_status = "submitted"

    user.save()

    # Create (or update) the Company row from applied_company_* so the consultant
    # can see their own company in the Company Database tab.
    if applied_company_name:
        try:
            company, _ = Company.objects.get_or_create(
                tenant=user.tenant,
                name=applied_company_name,
                defaults={
                    "registration_id": applied_company_reg_number or None,
                    "country": applied_country_of_incorporation or None,
                    "website": applied_company_website or None,
                    "owner_user": user,
                    "consultant": user,
                },
            )
            update_fields = []
            if not company.consultant_id:
                company.consultant = user
                update_fields.append("consultant")
            if not company.owner_user_id:
                company.owner_user = user
                update_fields.append("owner_user")
            if applied_company_reg_number and not company.registration_id:
                company.registration_id = applied_company_reg_number
                update_fields.append("registration_id")
            if applied_country_of_incorporation and not company.country:
                company.country = applied_country_of_incorporation
                update_fields.append("country")
            if applied_company_website and not company.website:
                company.website = applied_company_website
                update_fields.append("website")
            if update_fields:
                company.save(update_fields=update_fields)

            if not user.primary_company_id:
                user.primary_company = company
                user.save(update_fields=["primary_company"])
        except IntegrityError:
            # Name collision within tenant that get_or_create couldn't resolve cleanly — skip.
            pass

    # Save Due Diligence data
    DueDiligence.objects.update_or_create(
        user=user,
        defaults={
            "criminal_offence": request.POST.get("dd1", "no"),
            "criminal_offence_details": request.POST.get("dd1_details", ""),
            "regulatory_sanctions": request.POST.get("dd2", "no"),
            "regulatory_sanctions_details": request.POST.get("dd2_details", ""),
            "is_pep": request.POST.get("dd3", "no"),
            "insolvency_history": request.POST.get("dd4", "no"),
            "insolvency_history_details": request.POST.get("dd4_details", ""),
            "sufficient_financial_resources": request.POST.get("dd5", "yes"),
            "pending_legal_disputes": request.POST.get("dd6", "no"),
            "pending_legal_disputes_details": request.POST.get("dd6_details", ""),
            "competitor_interest": request.POST.get("dd7", "no"),
            "competitor_interest_details": request.POST.get("dd7_details", ""),
            "contractual_obligations": request.POST.get("dd8", "no"),
            "contractual_obligations_details": request.POST.get("dd8_details", ""),
            "declared_truthful": request.POST.get("declared_truthful") == "on",
            "declared_update": request.POST.get("declared_update") == "on",
            "accepted_terms": request.POST.get("accepted_terms") == "on",
            "consented_aml": request.POST.get("consented_aml") == "on",
        },
    )

    return redirect("apply-review")


@login_required
def apply_review_view(request):
    user = request.user

    if not user.role or not user.role.code:
        messages.error(request, "Your account does not have a valid role assigned. Please contact support.")
        return redirect("login")

    role_code = user.role.code.lower()
    if 'consultant' in role_code:
        role_label = 'Consultant'
    elif 'coordinator' in role_code:
        role_label = 'Coordinator'
    elif 'franchise' in role_code:
        role_label = 'Franchise Partner'
    else:
        messages.error(request, "Invalid role for application review.")
        return redirect("dashboard")

    return render(request, "auth/apply_review.html", {
        "role_label": role_label,
    })


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "auth/forgot_password.html")

        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
            messages.error(request, "Enter a valid email address.")
            return render(request, "auth/forgot_password.html")

        # Always show success to prevent email enumeration
        success_msg = "If an account with that email exists, we've sent a verification code."

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            try:
                # Invalidate any existing OTPs for this user
                PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

                # Generate a 6-digit OTP
                otp = f"{random.SystemRandom().randint(0, 999999):06d}"
                expires_at = timezone.now() + timedelta(minutes=10)

                PasswordResetToken.objects.create(
                    user=user,
                    token=otp,
                    expires_at=expires_at,
                )

                send_otp_email(
                    to_email=user.email,
                    first_name=user.first_name,
                    otp=otp,
                )
            except Exception as e:
                logger.error("Failed to send OTP email to %s: %s", email, e)
                messages.error(request, "Something went wrong while sending the verification code. Please try again.")
                return render(request, "auth/forgot_password.html")

        # Store email in session for the OTP verification step
        request.session["reset_email"] = email

        messages.success(request, success_msg)
        return redirect("verify-otp")

    return render(request, "auth/forgot_password.html")


def verify_otp(request):
    email = request.session.get("reset_email")
    if not email:
        return redirect("forgot-password")

    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()

        if not otp or len(otp) != 6:
            messages.error(request, "Please enter a valid 6-digit code.")
            return render(request, "auth/verify_otp.html", {"email": email})

        reset_token = PasswordResetToken.objects.filter(
            user__email__iexact=email,
            token=otp,
            is_used=False,
        ).first()

        if not reset_token or not reset_token.is_valid():
            messages.error(request, "Invalid or expired code. Please try again.")
            return render(request, "auth/verify_otp.html", {"email": email})

        # Mark OTP as used so it cannot be reused
        reset_token.is_used = True
        reset_token.save(update_fields=["is_used"])

        # OTP verified — store token ID in session for the reset step
        request.session["reset_token_id"] = str(reset_token.id)
        return redirect("reset-password")

    return render(request, "auth/verify_otp.html", {"email": email})


def reset_password(request):
    token_id = request.session.get("reset_token_id")
    if not token_id:
        return redirect("forgot-password")

    reset_token = PasswordResetToken.objects.select_related("user").filter(id=token_id).first()
    if not reset_token or timezone.now() >= reset_token.expires_at:
        request.session.pop("reset_token_id", None)
        request.session.pop("reset_email", None)
        return render(request, "auth/reset_password.html", {"invalid_token": True})

    if request.method == "POST":
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "auth/reset_password.html")

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/reset_password.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/reset_password.html")

        user = reset_token.user
        user.set_password(password)
        user.save(update_fields=["password"])

        # Clean up session
        request.session.pop("reset_token_id", None)
        request.session.pop("reset_email", None)

        messages.success(request, "Your password has been reset successfully. You can now log in.")
        return redirect("login")

    return render(request, "auth/reset_password.html")
