import logging
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import UserRole, Permission

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


from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme

def admin_login(request):
    if request.user.is_authenticated:
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("dashboard")

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Invalid credentials")
            return render(request, "auth/login.html")

        if not user.is_active:
            messages.error(request, "Your account is inactive")
            return render(request, "auth/login.html")

        login(request, user)

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)

        if user.is_superuser or (user.role and user.role.name == "tenant_admin"):
            return redirect("dashboard")

        # Check subscription status for business users
        from billing.models import Subscription
        pending_sub = Subscription.objects.filter(user=user, status="created").first()
        if pending_sub:
            messages.info(request, "Your subscription is pending admin approval. You will be able to access the dashboard once approved.")
            return render(request, "auth/pending_approval.html", {"subscription": pending_sub})

        active_sub = Subscription.objects.filter(user=user, status="active").first()
        if active_sub:
            return redirect("dashboard")

        return redirect("membership")

    return render(request, "auth/login.html")


def admin_logout(request):
    logout(request)
    return redirect("login")


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from accounts.models import Tenant, Company, Role, UserCompany, User, DueDiligence
from accounts.constants import CountryChoices, LanguageChoices


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

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "auth/register.html", ctx)

        # email exists check
        if User.objects.filter(email=email).exists():
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

        # create user
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            tenant=tenant,
            role=role,
            phone=phone,
            country=country,
        )

        # "Others" is only valid for business_user role
        if company_id == "others" and role_name != "business_user":
            company_id = ""

        # link company (skip if user selected "others" — they'll create one later)
        if company_id and company_id != "others":
            company = Company.objects.filter(id=company_id).first()
            if company:
                user.primary_company = company
                user.save()

                UserCompany.objects.create(
                    user=user,
                    company=company,
                    is_primary=True
                )

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        # All roles go through Veriff identity verification
        # After verification, consultant/coordinator/franchise → /apply/, others → /membership/
        return redirect("/verify/")

    return render(request, "auth/register.html", ctx)

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def identity_verification_view(request):
    user = request.user

    if not user.role or not user.role.code:
        messages.error(request, "Your account does not have a valid role assigned. Please contact support.")
        return redirect("login")

    role_code = user.role.code.lower()
    show_apply_link = role_code in ('consultant', 'coordinator', 'franchise')

    return render(
        request,
        "auth/verify.html",
        {
            "VERIFF_PUBLIC_KEY": settings.VERIFF_API_KEY,
            "show_apply_link": show_apply_link,
        }
    )


@login_required
def apply_view(request):
    user = request.user
    role_value = ''
    role_label = ''
    role_icon = ''

    if user.role:
        role_code = user.role.code.lower() if user.role.code else ''
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

    return render(request, "auth/apply.html", {
        "role_value": role_value,
        "role_label": role_label,
        "role_icon": role_icon,
    })


@login_required
def apply_submit(request):
    if request.method != "POST":
        return redirect("apply")

    user = request.user

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
    }
    missing = [name for name, value in required_fields.items() if not value]
    if missing:
        messages.error(request, f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} required.")
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
    user.applied_year_founded = int(year_founded) if year_founded else None
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
import random
from datetime import timedelta
from django.utils import timezone
from accounts.models import User, PasswordResetToken
from accounts.utils.mailer import send_otp_email


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, "Email is required.")
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
