from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from accounts.models import UserRole, Permission

# def admin_login(request):
#     if request.user.is_authenticated:
#         return redirect("admin:dashboard")

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
#             return redirect("admin:dashboard")

#         try:
#             user_role = UserRole.objects.select_related("role").get(user=user)
#             if user_role.role.name == "tenant_admin":
#                 login(request, user)
#                 return redirect("admin:dashboard")
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
        return redirect("admin:dashboard")

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

        if user.is_superuser:
            login(request, user)
            return redirect("admin:dashboard")

        if not user.role:
            messages.error(
                request,
                "You are not allowed to access the admin panel"
            )
            return render(request, "auth/login.html")

        if user.role.name == "tenant_admin":
            login(request, user)
            return redirect("admin:dashboard")

        messages.error(
            request,
            "You are not allowed to access the admin panel"
        )

    return render(request, "auth/login.html")


def admin_logout(request):
    logout(request)
    return redirect("admin:login")



def register_view(request):
    return render(request, "auth/register.html")



from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.db import transaction

from accounts.models import User, Role, UserRole, UserCompany, UserCompanyRole, Tenant, Company

class RegisterView(View):

    template_name = "auth/register.html"

def get(self, request):
    return render(request, self.template_name)


@transaction.atomic
def post(self, request):

    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    email = request.POST.get("email")
    phone = request.POST.get("phone")
    country = request.POST.get("country")
    preferred_language = request.POST.get("preferred_language")
    password = request.POST.get("password")

    role_type = request.POST.get("role")
    company_name = request.POST.get("company_name")
    bio = request.POST.get("bio")


    role_map = {
        "business_user": "company_admin",
        "consultant": "consultant",
        "coordinator": "coordinator",
        "partner": "partner"
    }

    role = Role.objects.get(name=role_map[role_type])


    tenant = None
    company = None


    # BUSINESS USER → CREATE TENANT + COMPANY
    if role_type == "business_user":

        tenant = Tenant.objects.create(
            name=company_name
        )

        company = Company.objects.create(
            tenant=tenant,
            name=company_name
        )


    # OTHER ROLES → PLATFORM TENANT
    else:

        tenant = Tenant.objects.first()


    user = User.objects.create(
        tenant=tenant,
        role=role,
        primary_company=company,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        country=country,
        preferred_language=preferred_language,
        bio=bio
    )

    user.set_password(password)
    user.save()


    # GLOBAL USER ROLE
    UserRole.objects.create(
        user=user,
        role=role
    )


    # COMPANY RELATION
    if company:

        uc = UserCompany.objects.create(
            user=user,
            company=company,
            is_primary=True
        )

        UserCompanyRole.objects.create(
            user_company=uc,
            role=role
        )


    login(request, user)

    return redirect("/dashboard/")

