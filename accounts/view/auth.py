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

# Franchise tiers offered at registration (franchise role only). Stored verbatim
# on User.franchise_type (a free CharField). The first value is the canonical
# label shown in the apply mask and the admin Applications queue.
FRANCHISE_TYPES = (
    "Master Franchise",
    "National Franchise",
    "Regional Franchise",
    "Micro Franchise",
)

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

        # Notify EVERY active consultant that a new business user is using the
        # system, surfacing the details they just filled in (and a link to the
        # Users directory to view the full profile). Scoped to business-user
        # signups — those are the prospective clients a consultant follows up
        # with. Wrapped so a notification hiccup never breaks sign-up.
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

    from FontEsin.middleware.require_verification import GATE_PASS_STATUSES

    # Move the user straight to the next step as soon as they've SUBMITTED to
    # Veriff (status "submitted") or been approved — no waiting on Veriff's
    # async decision. Consultant/coordinator/franchise → application form;
    # everyone else → plan selection. The final decision keeps updating in the
    # DB via the webhook; if it comes back declined/resubmission, the gate
    # re-catches them on a later request.
    current_status = (user.verification_status or "")
    if current_status in GATE_PASS_STATUSES:
        return redirect("apply" if show_apply_link else "membership")

    # Not submitted yet (pending / cancelled / declined / expired). As a
    # safety net for a just-finished user whose "submitted" event webhook
    # hasn't landed yet, pull the latest decision straight from Veriff once;
    # if that already shows them past the gate, forward them on.
    from accounts.view.veriff import sync_veriff_decision
    synced = sync_veriff_decision(user)
    if synced:
        user.refresh_from_db(fields=["verification_status"])
        if (user.verification_status or "") in GATE_PASS_STATUSES:
            return redirect("apply" if show_apply_link else "membership")

    # Otherwise show the start screen so they can begin / re-attempt.
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

    # The application is now just a region (single country) selection — plus a
    # franchise-type choice for franchise partners. Everything else from the
    # old multi-page form was dropped per product decision. The selected country
    # ISO code drives the coordinator's territory scope (see
    # coordinator_territory_q); we store it on territory_country (+ the readable
    # label on target_region) at submit time.
    selected_country = (user.territory_country or "").strip().upper()

    return render(request, "auth/apply.html", {
        "role_value": role_value,
        "role_label": role_label,
        "role_icon": role_icon,
        "country_choices": CountryChoices.CHOICES,
        "franchise_types": FRANCHISE_TYPES,
        "selected_country": selected_country,
        "selected_franchise_type": (user.franchise_type or "").strip(),
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
    is_franchise = "franchise" in role_code
    if not any(r in role_code for r in ('consultant', 'coordinator', 'franchise')):
        messages.error(request, "The application is only available for consultants, coordinators, and franchise partners.")
        return redirect("dashboard")

    # The application is now just a single-country region selection (plus a
    # franchise-type choice for franchise partners). The country ISO code drives
    # the coordinator's territory scope.
    region_code = request.POST.get("region_country", "").strip().upper()
    franchise_type = request.POST.get("franchise_type", "").strip()

    valid_codes = {code for code, _ in CountryChoices.CHOICES}
    if region_code not in valid_codes:
        messages.error(request, "Please select your region (country).")
        return redirect("apply")

    if is_franchise and franchise_type not in FRANCHISE_TYPES:
        messages.error(request, "Please select your franchise type.")
        return redirect("apply")

    # Map the ISO code to its readable label for display/notifications.
    region_label = dict(CountryChoices.CHOICES).get(region_code, region_code)

    # territory_country (the explicit ISO code) is what coordinator_territory_q
    # reads first, so the coordinator immediately sees the right region once
    # approved. target_region keeps the human-readable label for the admin
    # Applications queue and the submission notification.
    user.territory_country = region_code
    user.target_region = region_label
    if is_franchise:
        user.franchise_type = franchise_type
    user.application_status = "submitted"
    user.save(update_fields=[
        "territory_country", "target_region", "franchise_type",
        "application_status", "updated_at",
    ])

    # All three staff roles now require super-admin approval — notify every
    # superuser so they can review it in the Applications queue.
    try:
        from accounts.utils.notifications import notify_application_submitted
        notify_application_submitted(user)
    except Exception:
        pass

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
