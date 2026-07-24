from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.utils.translation import gettext as _


class RequireCompanyForBusinessUserMiddleware:
    """Force a Business User who owns no company to create one before using
    the app.

    Plans are now company-scoped and everything a Business User does hangs off
    a company, so company creation is the mandatory first step after identity
    verification (it replaced the old "pick a plan" gate). A verified BU lands
    in the system on the Free floor and is bounced to the Company Database —
    where the "Add Company" modal lives — until they own at least one company.
    Once they do, this gate stops firing and the normal flow (request
    certification → select a plan) takes over.

    Skipped: superusers, tenant admins, and every non-BU role (consultants,
    coordinators, franchises don't create their own company here). The identity
    verification gate runs BEFORE this one, so an unverified BU is handled there
    first.
    """

    # Paths a company-less business user may still hit. Everything else
    # redirects to the dashboard, whose "Set Up Your Company" panel is the
    # create/join-company prompt (the mandatory onboarding step).
    _ALLOWED_URL_NAMES = (
        "dashboard",          # hosts the "Set Up Your Company" panel
        "companies",          # Company Database — also hosts the Add Company modal
        "my-companies",       # their (soon-to-exist) company list
        "profile",            # profile also exposes a Create Company form
        "profile-company-search",
        "logout",
        "login",
        "register",
        "identity-verification",
        "verify-otp",
        "forgot-password",
        "reset-password",
        "check-email",
        # Public marketing pages reachable from the top navigation.
        "home",
        "home_root",
        "worldmap",
        "about",
        "career",
        "contact",
        "set_language",
    )

    _ALLOWED_PREFIXES = (
        "/static/",
        "/media/",
        "/admin/",
        "/veriff/",
        "/i18n/",
        # Read-only NACE/NAICS autocomplete used BY the Add Company form itself —
        # a company-less BU must reach it to pick a classification, otherwise the
        # AJAX call gets bounced to /dashboard/ and the picker returns no results.
        "/api/industry-codes/",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self._allowed_paths = self._resolve_allowed_paths()

    def _resolve_allowed_paths(self):
        paths = set()
        for name in self._ALLOWED_URL_NAMES:
            try:
                paths.add(reverse(name))
            except NoReverseMatch:
                continue
        return paths

    def __call__(self, request):
        if not self._needs_redirect(request):
            return self.get_response(request)
        try:
            response = redirect("dashboard")
        except NoReverseMatch:
            return self.get_response(request)
        # Explain the bounce instead of silently landing on the dashboard: the
        # gated section (e.g. Request a Franchise) needs a company first. Only
        # message on a real page navigation so AJAX/asset fetches don't stack
        # duplicate alerts before the dashboard renders.
        self._notify_company_required(request)
        return response

    def _notify_company_required(self, request):
        if request.method != "GET":
            return
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return
        if "text/html" not in request.headers.get("accept", ""):
            return
        text = _(
            "Please create your company first — you can access this section "
            "once you have at least one company."
        )
        messages.warning(request, text)

    def _needs_redirect(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return False

        role = getattr(user, "role", None)
        role_code = ((role.code or "") if role else "").lower()
        if role_code != "business_user":
            return False

        path = request.path or ""
        if path in self._allowed_paths:
            return False
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return False

        # Lazy import to avoid circulars during app loading.
        from accounts.models import Company
        owns_company = Company.objects.filter(owner_user=user).exists()
        return not owns_company
