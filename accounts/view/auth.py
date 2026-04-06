from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import UserRole, Permission

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

def admin_login(request):
    if request.user.is_authenticated:
        next_url = request.GET.get("next")
        if next_url:
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
        if next_url:
            return redirect(next_url)

        if user.is_superuser or (user.role and user.role.name == "tenant_admin"):
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

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        country = request.POST.get("country")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        role_name = request.POST.get("role")
        company_id = request.POST.get("company_id")

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
    show_apply_link = False
    user = request.user
    if user.role and user.role.code:
        role_code = user.role.code.lower()
        if role_code in ('consultant', 'coordinator', 'franchise'):
            show_apply_link = True

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

    # Personal info
    user.first_name = request.POST.get("first_name", user.first_name)
    user.last_name = request.POST.get("last_name", user.last_name)
    user.birth_date = request.POST.get("birth_date") or None
    user.nationality = request.POST.get("nationality", "")
    user.phone = request.POST.get("phone", user.phone)
    user.linkedin_url = request.POST.get("linkedin_url", "")
    user.address_line1 = request.POST.get("address_line1", "")

    # Professional background
    user.current_position = request.POST.get("current_position", "")
    user.years_of_experience = request.POST.get("years_of_experience", "")
    user.primary_industry = request.POST.get("primary_industry", "")
    user.professional_summary = request.POST.get("professional_summary", "")

    # Company info
    user.applied_company_name = request.POST.get("applied_company_name", "")
    user.applied_company_reg_number = request.POST.get("applied_company_reg_number", "")
    user.applied_country_of_incorporation = request.POST.get("applied_country_of_incorporation", "")
    user.applied_legal_form = request.POST.get("applied_legal_form", "")
    year_founded = request.POST.get("applied_year_founded", "")
    user.applied_year_founded = int(year_founded) if year_founded else None
    user.applied_num_employees = request.POST.get("applied_num_employees", "")
    user.applied_company_website = request.POST.get("applied_company_website", "")

    # Role-specific
    user.target_region = request.POST.get("target_region", "")
    user.franchise_type = request.POST.get("franchise_type", "")
    user.motivation = request.POST.get("motivation", "")
    user.network_connections = request.POST.get("network_connections", "")
    user.expected_companies = request.POST.get("expected_companies", "")
    user.reference_1 = request.POST.get("reference_1", "")
    user.reference_2 = request.POST.get("reference_2", "")

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
    role_label = 'Consultant'

    if user.role and user.role.code:
        role_code = user.role.code.lower()
        if 'consultant' in role_code:
            role_label = 'Consultant'
        elif 'coordinator' in role_code:
            role_label = 'Coordinator'
        elif 'franchise' in role_code:
            role_label = 'Franchise Partner'

    return render(request, "auth/apply_review.html", {
        "role_label": role_label,
    })