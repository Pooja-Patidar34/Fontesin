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
from django.contrib.auth import get_user_model, login
from accounts.models import Tenant, Company, Role, UserCompany
from accounts.models import User


def register_view(request):

    companies = Company.objects.filter(is_active=True)

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
            return render(request, "auth/register.html", {"companies": companies})

        # password match check
        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "auth/register.html", {"companies": companies})

        tenant, _ = Tenant.objects.get_or_create(name="Default")

        role = Role.objects.filter(name__iexact=role_name).first()

        if not role:
            messages.error(request, "Invalid role selected")
            return render(request, "auth/register.html", {"companies": companies})

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

        # link company
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

        # ✅ THIS IS REQUIRED
        login(request, user)

        # redirect to verification step
        return redirect("/admin/verify/")

    return render(request, "auth/register.html", {"companies": companies})

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def identity_verification_view(request):

    return render(
        request,
        "auth/verify.html",
        {
            "VERIFF_PUBLIC_KEY": settings.VERIFF_API_KEY
        }
    )


import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from accounts.models import User, PasswordResetToken


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        # Always show success to prevent email enumeration
        success_msg = "If an account with that email exists, we've sent a verification code."

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
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

            send_mail(
                subject="FONTESIN – Your password reset code",
                message=(
                    f"Hi {user.first_name},\n\n"
                    f"We received a request to reset your password. "
                    f"Use the following verification code:\n\n"
                    f"    {otp}\n\n"
                    f"This code expires in 10 minutes.\n\n"
                    f"If you didn't request this, you can safely ignore this email.\n\n"
                    f"– FONTESIN Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        # Store email in session for the OTP verification step
        request.session["reset_email"] = email

        messages.success(request, success_msg)
        return redirect("admin:verify-otp")

    return render(request, "auth/forgot_password.html")


def verify_otp(request):
    email = request.session.get("reset_email")
    if not email:
        return redirect("admin:forgot-password")

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

        # OTP verified — store token ID in session for the reset step
        request.session["reset_token_id"] = str(reset_token.id)
        return redirect("admin:reset-password")

    return render(request, "auth/verify_otp.html", {"email": email})


def reset_password(request):
    token_id = request.session.get("reset_token_id")
    if not token_id:
        return redirect("admin:forgot-password")

    reset_token = PasswordResetToken.objects.filter(id=token_id, is_used=False).first()
    if not reset_token or not reset_token.is_valid():
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
        user.save()

        reset_token.is_used = True
        reset_token.save()

        # Clean up session
        request.session.pop("reset_token_id", None)
        request.session.pop("reset_email", None)

        messages.success(request, "Your password has been reset successfully. You can now log in.")
        return redirect("admin:login")

    return render(request, "auth/reset_password.html")