import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext as _
from accounts.models import Tenant, Company, UserCompany
from accounts.constants import (
    CompanyClassificationChoices,
    CompanyEntityTypeChoices,
    CountryChoices,
    EmployeeCountRangeChoices,
    SupportedLocale,
    COUNTRY_CODES,
    COUNTRY_STATES,
)
import datetime
from FontEsin.middleware.locale import apply_language_cookie, normalize_locale
from FontEsin.templatetags.i18n_extras import LANGUAGE_DISPLAY_NAMES

CLASSIFICATION_CODES = {code for code, _ in CompanyClassificationChoices.CHOICES}
ENTITY_TYPE_CODES = {code for code, _ in CompanyEntityTypeChoices.CHOICES}
EMPLOYEE_RANGE_CODES = {code for code, _ in EmployeeCountRangeChoices.CHOICES}
COUNTRY_LABELS = dict(CountryChoices.CHOICES)

# Reused on the profile-page Create Company form (mirrors the modal in companies.html).
HOUSE_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/ ]{0,14}$")
REGION_DISTRICT_RE = re.compile(r"^(?=.*[A-Za-z0-9])[A-Za-zÀ-ɏ0-9\s,./&'\-]{1,120}$")
INDUSTRY_CODE_RE = re.compile(r"^[A-Za-z0-9.\-]{1,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LOGO_ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif")
LOGO_MAX_BYTES = 5 * 1024 * 1024
from billing.plan_i18n import localized_plan_name
from billing.utils import (
    get_user_plan,
    get_active_subscription,
    get_pending_subscription,
    get_deactivated_paid_plan,
)


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"

# First / last name: 2-50 chars, letters (incl. accented) + spaces/hyphens/apostrophes/periods.
NAME_RE = re.compile(r"^[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ\s'\-.]{1,49}$")

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
def plans_view(request):
    """Standalone Plans page — renders the user's active plan card, the
    pending-upgrade card, and below them the full subscription history.

    Folds the former /plan-history/ table into the same page so users have
    one place to see "what plan am I on now" and "what plans have I been
    on". The plan card markup is shared via ``profile/_plan_card.html`` so
    Profile and Plans never drift. History rows are paginated server-side
    via ?page=.
    """
    from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
    from billing.models import Subscription

    user = request.user
    role_code = (user.role.code or "").lower() if user.role else ""
    # Mirror the profile-card visibility: superusers and staff roles don't
    # have subscriptions, so the dedicated page should also refuse them.
    if user.is_superuser or role_code in ("consultant", "coordinator", "franchise"):
        raise PermissionDenied("Plans are only available to subscribing users.")

    # Plans are company-scoped, so this page is about the ACTIVE company (the
    # one selected in the switcher). Resolve it so the current-plan card AND the
    # history below both reflect that single company — not a mix across every
    # company the user owns.
    from billing.utils import resolve_active_company
    active_company = resolve_active_company(user)

    subscription = get_active_subscription(user, company=active_company)
    deactivated_plan = get_deactivated_paid_plan(
        user, subscription=subscription, company=active_company
    )
    if deactivated_plan:
        messages.warning(
            request,
            _("Your %(plan)s plan was deactivated by the admin. "
              "You have been moved to the Free plan. "
              "Please activate another plan to continue.")
            % {"plan": localized_plan_name(deactivated_plan)},
        )

    # Subscription history for the ACTIVE company only (newest first). Without
    # this scope the table mixes every company's plans together — e.g. company
    # B's Pro plan would show on company A's page. Legacy account-level subs
    # (no company) fall back to a user scope.
    history_qs = (
        Subscription.objects
        .filter(company=active_company)
        if active_company else
        Subscription.objects.filter(user=user, company__isnull=True)
    )
    history_qs = history_qs.select_related("plan", "user", "company").order_by(
        "-start_date", "-created_at"
    )
    paginator = Paginator(history_qs, 10)
    try:
        page_obj = paginator.page(request.GET.get("page", 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    return render(
        request,
        "dashboard/plans.html",
        {
            "active_menu": "plans",
            "user_plan": get_user_plan(user, subscription=subscription),
            "subscription": subscription,
            "pending_subscription": get_pending_subscription(user, company=active_company),
            "deactivated_plan": deactivated_plan,
            "subscriptions": page_obj,
            "page_obj": page_obj,
            "plan_company": active_company,
        },
    )


@login_required
def company_search_ajax(request):
    """Type-ahead search for the 'Join existing company' picker on the profile
    page. Limited to 20 hits, name LIKE — server-side so the dropdown scales
    past a small directory.

    Scoped to the user's PLAN, matching the Company Database:
        free   → registered country
        basic  → registered country
        pro    → country's region (group of countries)
        global → worldwide
    So a business user can only request to join companies within their plan's
    geographic reach. No plan scope (e.g. no plan / no country set) → no
    joinable companies, mirroring the discovery list.
    """
    q = (request.GET.get("q") or "").strip()

    # Reuse the Company Database's plan-based geographic scope (it already pins
    # is_active=True). Local import avoids a circular import at module load.
    from accounts.view.company import business_user_plan_scope_q
    scope_q = business_user_plan_scope_q(request.user)
    if scope_q is None:
        return JsonResponse({"results": []})

    qs = Company.objects.filter(scope_q)
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("name").values("id", "name", "city", "country", "classification").distinct()[:20]

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
    # The "My Company" panel reflects the company the user is currently acting
    # as — the one picked in the company switcher — not just their
    # primary_company, so switching companies updates what's shown here too.
    # Falls back to primary_company when there's no active selection or for
    # non-business roles.
    role_code = (user.role.code or "").lower() if user.role else ""
    if role_code == "business_user":
        from billing.utils import resolve_active_company
        user_company = resolve_active_company(user) or user.primary_company
    else:
        user_company = user.primary_company
    # A company soft-deleted by the admin must not appear ANYWHERE — including
    # the profile "My Company" panel (list views already filter is_deleted).
    # Treat a deleted company as "no company" so the user sees the Set-Up /
    # Join prompt instead.
    if user_company and user_company.is_deleted:
        user_company = None

    if request.method == "POST":
        form_type = request.POST.get("form_type", "")

        # ---- Request to join an existing company ----
        # A business user picks a company and we send a join request to that
        # company's owner. The owner approves/declines from the Join Requests
        # tab; on approval the user is linked via UserCompany (see
        # accounts/view/join_request.py). This replaces the former instant-link
        # behaviour — joining now always goes through owner approval.
        if form_type == "join_company":
            ajax = _is_ajax(request)

            def _join_fail(msg, status=400):
                if ajax:
                    return JsonResponse({"ok": False, "message": msg}, status=status)
                messages.error(request, msg)
                return redirect("profile")

            company_id = (request.POST.get("company_id") or "").strip()
            if not company_id:
                return _join_fail(_("Please select a company to join."))

            company = Company.objects.filter(id=company_id).first()
            if not company:
                return _join_fail(_("That company is unavailable. Please pick another."))

            from accounts.view.join_request import create_join_request, JoinRequestError
            try:
                create_join_request(
                    user, company, message=request.POST.get("message")
                )
            except JoinRequestError as e:
                return _join_fail(e.message, status=e.status)

            success_msg = _(
                "Join request sent to %(company)s. You'll be linked once "
                "the company owner approves it."
            ) % {"company": company.name}
            if ajax:
                return JsonResponse({"ok": True, "message": success_msg})
            messages.success(request, success_msg)
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
                return _fail(_("Enter a valid first name (2-50 characters; letters, spaces, hyphens, apostrophes)."))
            if not last_name or not NAME_RE.match(last_name):
                return _fail(_("Enter a valid last name (2-50 characters; letters, spaces, hyphens, apostrophes)."))

            if phone:
                if not PHONE_CHARSET_RE.match(phone):
                    return _fail(_("Phone may only contain digits and the symbols + - ( ) and spaces (7-25 characters)."))
                digits = re.sub(r"\D", "", phone)
                if not (5 <= len(digits) <= 15):
                    return _fail(_("Phone must contain 5-15 digits."))

            if country and country not in COUNTRY_CODES:
                return _fail(_("Please select a valid country from the list."))

            preferred_language_raw = request.POST.get("preferred_language")
            if preferred_language_raw is not None:
                preferred_language_raw = preferred_language_raw.strip()
                if preferred_language_raw and preferred_language_raw not in SupportedLocale.ALL:
                    return _fail(_("Please select a valid language."))
                preferred_language = (
                    normalize_locale(preferred_language_raw)
                    if preferred_language_raw
                    else SupportedLocale.EN
                )
            else:
                preferred_language = user.preferred_language or SupportedLocale.EN

            # Snapshot the contact fields BEFORE we mutate `user` so the
            # post-save fan-out below can detect a real change (vs a no-op
            # POST that just resubmits the same values).
            old_first = user.first_name
            old_last = user.last_name
            old_phone = user.phone or ""
            old_language = user.preferred_language or SupportedLocale.EN

            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone or None
            user.country = country or None
            language_changed = preferred_language != old_language
            user.persist_preferred_language(preferred_language)
            user.save(update_fields=["first_name", "last_name", "phone", "country", "updated_at"])

            # Consultants are the visible "Certifying Consultant" on the
            # companies they approved. When they edit their contact info,
            # the Company view modal already auto-reflects the change (the
            # data is FK-derived). Notify each affected Business User so
            # they can see the change in their Notifications tab too.
            try:
                role_code_lc = (user.role.code or "").lower() if user.role else ""
            except Exception:
                role_code_lc = ""
            if role_code_lc == "consultant":
                changed = (
                    (first_name != old_first)
                    or (last_name != old_last)
                    or ((phone or "") != old_phone)
                )
                if changed:
                    try:
                        from accounts.utils.notifications import notify
                        from accounts.utils.i18n_messages import Msg
                        from accounts.models import Notification

                        full_name = f"{first_name} {last_name}".strip() or user.email
                        certified = (
                            Company.objects
                            .filter(certified_by=user)
                            .select_related("owner_user")
                        )
                        for comp in certified:
                            owner = comp.owner_user
                            if not owner or owner.id == user.id:
                                continue
                            notify(
                                recipient=owner,
                                sender=user,
                                kind=Notification.KIND_GENERIC,
                                title=Msg("Your certifying consultant's contact info was updated"),
                                body=Msg(
                                    "%(name)s updated their contact information. "
                                    "You can see the latest details on the %(company)s company view.",
                                    name=full_name, company=comp.name,
                                ),
                                related_company=comp,
                            )
                    except Exception:
                        # Never block the profile save on a notification error.
                        pass

            if ajax:
                response = JsonResponse({
                    "ok": True,
                    "message": _("Profile updated successfully."),
                    "language_changed": language_changed,
                    "user": {
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "phone": user.phone or "",
                        "country": user.country or "",
                        "preferred_language": user.preferred_language,
                        "preferred_language_display": LANGUAGE_DISPLAY_NAMES.get(
                            user.preferred_language, user.preferred_language
                        ),
                    },
                })
                if language_changed:
                    apply_language_cookie(response, preferred_language)
                return response

            messages.success(request, _("Profile updated successfully."))
            response = redirect("profile")
            if language_changed:
                apply_language_cookie(response, preferred_language)
            return response

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

        # New BU-onboarding fields. Mirrors the modal in companies.html so the
        # certification request carries the same info no matter where it's
        # filed from.
        entity_type = request.POST.get("entity_type", "").strip()
        year_established_raw = request.POST.get("year_established", "").strip()
        employee_count_range = request.POST.get("employee_count_range", "").strip()
        region = request.POST.get("region", "").strip()
        district = request.POST.get("district", "").strip()
        house_number = request.POST.get("house_number", "").strip()
        industry_code = request.POST.get("industry_code", "").strip()
        keywords = request.POST.get("keywords", "").strip()
        contact_email = request.POST.get("contact_email", "").strip()
        logo_file = request.FILES.get("logo")

        # Helper: fail validation on the Create-Company form. Stashes the
        # error keyed by field so the template can render it inline next to
        # the offending input (instead of only as a top-of-page toast), and
        # flags the "Create New Company" tab to stay open after the
        # redirect — otherwise the default "Join Existing" tab takes over
        # and the user thinks the form vanished.
        def _fail_create_company(message, field=None):
            messages.error(request, message)
            errors = request.session.get("create_company_errors") or {}
            if field:
                errors[field] = message
            else:
                errors.setdefault("_form", message)
            request.session["create_company_errors"] = errors
            request.session["open_create_company_tab"] = True
            return redirect("profile")

        # Stash the cleaned values so a validation-failure redirect can
        # repopulate the form on the next GET — losing every field on a
        # single duplicate-domain (or any other) error is hostile UX. The
        # session entry is consumed and removed by the GET branch below.
        # Note: `logo_file` is intentionally not persisted in the session —
        # UploadedFile isn't JSON-serializable and the user will have to
        # re-select the file on error.
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
            "entity_type": entity_type,
            "year_established": year_established_raw,
            "employee_count_range": employee_count_range,
            "region": region,
            "district": district,
            "house_number": house_number,
            "industry_code": industry_code,
            "keywords": keywords,
            "contact_email": contact_email,
        }

        if not company_name:
            return _fail_create_company(_("Company name is required."), field="company_name")

        if not COMPANY_NAME_RE.match(company_name):
            return _fail_create_company(
                _("Company name must be 2-100 characters and may only contain letters, digits, spaces, and the symbols & ' . , - ( )."),
                field="company_name",
            )

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
            return _fail_create_company(
                _("A company with this name already exists. Please choose a different name."),
                field="company_name",
            )

        if not registration_id:
            return _fail_create_company(_("Registration No. is required."), field="registration_id")

        if not REGISTRATION_ID_RE.match(registration_id):
            return _fail_create_company(
                _("Registration No. may only contain letters, digits, and the symbols - / . _ (2-100 characters)."),
                field="registration_id",
            )

        if Company.objects.filter(registration_id__iexact=registration_id).exists():
            return _fail_create_company(
                _("A company with this Registration No. already exists. Registration No. must be unique."),
                field="registration_id",
            )

        if not domain:
            return _fail_create_company(_("Domain is required."), field="domain")

        domain = domain.lower()
        if not DOMAIN_RE.match(domain):
            return _fail_create_company(
                _("Enter a valid domain like mycompany.com (4-253 characters, letters/digits/hyphens separated by dots, with a TLD of at least 2 letters)."),
                field="domain",
            )

        # Check if domain already exists (case-insensitive)
        if Tenant.objects.filter(domain__iexact=domain).exists():
            return _fail_create_company(_("This domain is already taken."), field="domain")

        if not classification:
            return _fail_create_company(_("Classification is required."), field="classification")

        if classification not in CLASSIFICATION_CODES:
            return _fail_create_company(
                _("Please select a valid classification from the list."),
                field="classification",
            )

        if website and not WEBSITE_URL_RE.match(website):
            return _fail_create_company(
                _("Enter a valid website URL like https://example.com (only letters, digits, and - . _ / in the path)."),
                field="website",
            )

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
                return _fail_create_company(err, field="company_phone")

        if phone_secondary:
            err = _validate_phone_like(phone_secondary, "Secondary phone")
            if err:
                return _fail_create_company(err, field="phone_secondary")

        if fax:
            err = _validate_phone_like(fax, "Fax")
            if err:
                return _fail_create_company(err, field="fax")

        if address_line1 and not ADDRESS_LINE_RE.match(address_line1):
            return _fail_create_company(
                _("Address line 1 may only contain letters, digits, spaces and the symbols , . - / # (3-120 characters)."),
                field="address_line1",
            )

        if address_line2 and not ADDRESS_LINE_RE.match(address_line2):
            return _fail_create_company(
                _("Address line 2 may only contain letters, digits, spaces and the symbols , . - / # (3-120 characters)."),
                field="address_line2",
            )

        if not city:
            return _fail_create_company(_("City is required."), field="city")

        if not CITY_NAME_RE.match(city):
            return _fail_create_company(
                _("City may only contain letters, spaces, hyphens, apostrophes and periods (2-60 characters)."),
                field="city",
            )

        # Country comes from the dropdown as an ISO-3166 alpha-2 code (e.g. "US").
        # State must be one of the known subdivisions for that country — both
        # selects are populated from the same map the server uses, so the only
        # way to get a value outside the map is a tampered request.
        if not country:
            return _fail_create_company(_("Country is required."), field="company_country")

        country_code = country.upper()
        if country_code not in COUNTRY_CODES:
            return _fail_create_company(
                _("Please select a valid country from the list."),
                field="company_country",
            )
        country = country_code

        valid_states = COUNTRY_STATES.get(country_code, [])
        if not state:
            return _fail_create_company(_("State is required."), field="state")

        if valid_states and state not in valid_states:
            return _fail_create_company(
                _("Please select a valid state for the chosen country."),
                field="state",
            )

        if postal_code and not POSTAL_CODE_RE.match(postal_code):
            return _fail_create_company(
                _("Postal code may only contain letters, digits, spaces and hyphens (3-12 characters)."),
                field="postal_code",
            )

        # ---- New BU-onboarding fields validation ----
        if entity_type and entity_type not in ENTITY_TYPE_CODES:
            return _fail_create_company(
                _("Please select a valid legal form from the list."),
                field="entity_type",
            )

        year_established = None
        if year_established_raw:
            try:
                year_established = int(year_established_raw)
            except ValueError:
                return _fail_create_company(
                _("Year of establishment must be a number."),
                    field="year_established",
                )
            current_year = datetime.date.today().year
            if year_established < 1500 or year_established > current_year:
                return _fail_create_company(
                    f"Year of establishment must be between 1500 and {current_year}.",
                    field="year_established",
                )

        if employee_count_range and employee_count_range not in EMPLOYEE_RANGE_CODES:
            return _fail_create_company(
                _("Please select a valid employee count range."),
                field="employee_count_range",
            )

        if region and not REGION_DISTRICT_RE.match(region):
            return _fail_create_company(_("Region contains invalid characters."), field="region")

        if district and not REGION_DISTRICT_RE.match(district):
            return _fail_create_company(_("District contains invalid characters."), field="district")

        if house_number and not HOUSE_NUMBER_RE.match(house_number):
            return _fail_create_company(
                _("House number may only contain letters, digits and the symbols - / and spaces (1-15 characters)."),
                field="house_number",
            )

        if industry_code and not INDUSTRY_CODE_RE.match(industry_code):
            return _fail_create_company(
                _("Industry code may only contain letters, digits, dots and hyphens (1-20 characters)."),
                field="industry_code",
            )

        if keywords and len(keywords) > 500:
            return _fail_create_company(
                _("Keywords must be 500 characters or fewer."),
                field="keywords",
            )

        if contact_email and not EMAIL_RE.match(contact_email):
            return _fail_create_company(
                _("Contact email is not a valid email address."),
                field="contact_email",
            )

        if logo_file:
            name = (logo_file.name or "").lower()
            if not name.endswith(LOGO_ALLOWED_EXTENSIONS):
                return _fail_create_company(
                _("Logo must be one of: ") + ", ".join(LOGO_ALLOWED_EXTENSIONS),
                    field="logo",
                )
            if getattr(logo_file, "size", 0) > LOGO_MAX_BYTES:
                return _fail_create_company(
                _("Logo file must be 5 MB or smaller."),
                    field="logo",
                )

        # Create tenant internally
        tenant = Tenant.objects.create(
            name=company_name,
            domain=domain,
        )

        # A consultant IS the certifying authority, so their own company needs
        # no certification — auto-certify it (active, certified by themselves,
        # consultant FK = them) and skip the broadcast. (Superusers likewise
        # self-certify.) Everyone else's company enters the certification queue
        # as "pending" and stays out of the public directory (is_active=False)
        # until a consultant approves it. This stops a consultant from getting
        # a certification request for a company they just created themselves.
        from django.utils import timezone
        creator_role = (user.role.code or "").lower() if user.role else ""
        self_certifies = user.is_superuser or creator_role == "consultant"

        company = Company.objects.create(
            tenant=tenant,
            name=company_name,
            registration_id=registration_id,
            classification=classification or None,
            entity_type=entity_type or None,
            website=website or None,
            phone=phone or None,
            phone_secondary=phone_secondary or None,
            fax=fax or None,
            address_line1=address_line1 or None,
            address_line2=address_line2 or None,
            house_number=house_number or None,
            district=district or None,
            region=region or None,
            city=city or None,
            state=state or None,
            postal_code=postal_code or None,
            country=country or None,
            year_established=year_established,
            industry_code=industry_code or None,
            keywords=keywords or None,
            employee_count_range=employee_count_range or None,
            contact_email=contact_email or None,
            logo=logo_file or None,
            certification_status="certified" if self_certifies else "pending",
            is_active=True if self_certifies else False,
            owner_user=user,
            consultant=user if creator_role == "consultant" else None,
            certified_by=user if self_certifies else None,
            certified_at=timezone.now() if self_certifies else None,
        )

        # Only non-self-certifying creators trigger the broadcast. The request
        # is visible to every active consultant via the certifications page;
        # the first one to approve claims ownership (consultant FK is set at
        # approval time in certification_action).
        if not self_certifies:
            try:
                from accounts.utils.notifications import notify_certification_request
                notify_certification_request(company, submitted_by=user)
            except Exception:
                pass

        # Link user to the new tenant and company
        user.tenant = tenant
        user.primary_company = company
        user.save()

        UserCompany.objects.get_or_create(
            user=user,
            company=company,
            defaults={"is_primary": True},
        )

        # Give the new company a Free plan so it behaves as Free-tier until the
        # owner selects a paid plan after certification (plans are
        # company-scoped — see billing.utils.ensure_free_subscription).
        try:
            from billing.utils import ensure_free_subscription
            ensure_free_subscription(company, user=user)
        except Exception:
            pass

        # Same backfill as the join-company branch: if this user already
        # had an approved paid subscription before they had a consultant-
        # linked company, no commission was created at the time. Now that
        # the routed consultant is attached, create the missing row(s) so
        # the admin commission panel reflects reality.
        if company.consultant_id:
            from billing.views import backfill_consultant_commissions_for_user
            backfill_consultant_commissions_for_user(user)

        request.session.pop("create_company_form", None)
        request.session.pop("create_company_errors", None)
        request.session.pop("open_create_company_tab", None)
        messages.success(
            request,
            _("Company created successfully.")
            if self_certifies
            else "Certification request submitted. A consultant will review your company shortly.",
        )
        return redirect("profile")

    subscription = get_active_subscription(user)
    deactivated_plan = get_deactivated_paid_plan(user, subscription=subscription)
    if deactivated_plan and request.method == "GET":
        # Surface the warning on the profile page too, so a user landing
        # straight here knows why their feature set just shrank.
        messages.warning(
            request,
            _("Your %(plan)s plan was deactivated by the admin. "
              "You have been moved to the Free plan. "
              "Please activate another plan to continue.")
            % {"plan": localized_plan_name(deactivated_plan)},
        )

    # Outgoing join requests this user has sent (pending / approved / declined)
    # so the profile page can show their status next to the join picker.
    from accounts.models import CompanyJoinRequest
    my_join_requests = (
        CompanyJoinRequest.objects
        .filter(user=user)
        .select_related("company")
        .order_by("-created_at")
    )

    # Whether the "join an existing company" picker should be offered. Open to
    # business users (any plan); roles that represent their own single company
    # register one instead. Available even when the user already has a company,
    # so they can join additional ones.
    role_code = (user.role.code or "").lower() if user.role else ""
    can_join_company = (
        not user.is_superuser and role_code == "business_user"
    )

    context = {
        "active_menu": "profile",
        "user_company": user_company,
        "my_join_requests": my_join_requests,
        "can_join_company": can_join_company,
        "classifications": CompanyClassificationChoices.CHOICES,
        "entity_types": CompanyEntityTypeChoices.CHOICES,
        "employee_count_ranges": EmployeeCountRangeChoices.CHOICES,
        "countries": CountryChoices.CHOICES,
        "language_choices": [(code, LANGUAGE_DISPLAY_NAMES[code]) for code, _ in SupportedLocale.CHOICES],
        "preferred_language": user.preferred_language or SupportedLocale.EN,
        "preferred_language_display": LANGUAGE_DISPLAY_NAMES.get(
            user.preferred_language or SupportedLocale.EN,
            user.preferred_language or SupportedLocale.EN,
        ),
        "country_states": COUNTRY_STATES,
        "user_plan": get_user_plan(user, subscription=subscription),
        "subscription": subscription,
        "pending_subscription": get_pending_subscription(user),
        "deactivated_plan": deactivated_plan,
        # Pop-and-render: the previous POST stashed cleaned values here on a
        # validation-failure redirect; consuming them now means a manual page
        # refresh starts with a blank form again.
        "create_company_form": request.session.pop("create_company_form", None),
        # Field-level errors keyed by input name (e.g. "registration_id" →
        # "A company with this Registration No. already exists..."). The
        # template renders each below its corresponding input so the user
        # sees the message next to the offending field — not just as a
        # top-of-page toast on a different tab.
        "create_company_errors": request.session.pop("create_company_errors", None) or {},
        # When the last submission failed, force the "Create New Company"
        # tab to be the active one on render. Otherwise the default "Join
        # Existing" tab takes over and the user thinks the form vanished.
        "open_create_company_tab": request.session.pop("open_create_company_tab", False),
    }
    return render(request, "profile/profile.html", context)
