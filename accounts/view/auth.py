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


from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from accounts.models import Tenant, Company, Role, UserCompany

User = get_user_model()

def register_view(request):

    # ✅ send companies to template (GET + POST fallback)
    companies = Company.objects.filter(is_active=True)

    if request.method == "POST":

        # -------------------------
        # PHASE 1 DATA
        # -------------------------
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        country = request.POST.get("country")
        password = request.POST.get("password")

        # -------------------------
        # PHASE 2 DATA
        # -------------------------
        role_name = request.POST.get("role")
        company_id = request.POST.get("company_id")  # ✅ NEW

        # -------------------------
        # VALIDATION
        # -------------------------
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return render(request, "auth/register.html", {"companies": companies})

        # -------------------------
        # TENANT
        # -------------------------
        tenant, _ = Tenant.objects.get_or_create(name="Default")

        # -------------------------
        # ROLE (better: no auto create)
        # -------------------------
        role = Role.objects.filter(name__iexact=role_name).first()

        # -------------------------
        # CREATE USER
        # -------------------------
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

        # -------------------------
        # COMPANY LINK (UPDATED)
        # -------------------------
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

        # -------------------------
        # SUCCESS
        # -------------------------
        messages.success(request, "Account created successfully")
        return redirect("admin:login")

    return render(request, "website/register.html", {"companies": companies})