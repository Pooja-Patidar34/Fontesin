from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


# Veriff verification states that count as fully "verified" (final approval).
VERIFIED_STATUSES = ("approved",)

# States that let an account PASS the identity gate (reach plan selection /
# dashboard). We let a user through as soon as they've "submitted" their
# documents to Veriff — they shouldn't have to sit and wait on Veriff's async
# decision. The decision still lands later via the webhook and updates
# verification_status in the DB; a "declined"/"resubmission_requested"/etc.
# result is NOT in this set, so once that lands the user is re-gated to
# /verify/ on their next request. "pending" (started but not submitted, or a
# cancelled attempt) is also not here — those stay on the start screen.
GATE_PASS_STATUSES = ("approved", "submitted")


class RequireIdentityVerificationMiddleware:
    """
    Force any signed-in account that hasn't passed Veriff onto the identity
    verification step until it does.

    register_view logs the new user in immediately and redirects them to
    /verify/, but nothing stopped them from then using the browser back
    button (or typing a URL) to reach /membership/, pick a plan, and land in
    the dashboard — skipping identity verification entirely. This middleware
    closes that gap: every request from an unverified user is bounced to
    /verify/, except a small allow-list of paths they need to run the Veriff
    flow, log out, or load static assets.

    This runs BEFORE RequireCompanyForBusinessUserMiddleware so verification is
    enforced ahead of the company-creation gate — you can't create a company
    (or later pick a per-company plan) until you're verified.

    Skipped accounts: anonymous users (login_required handles them),
    superusers, and tenant admins — none of them go through the Veriff
    registration flow, and existing accounts were grandfathered to
    "approved" in migration 0036 so they're never caught here.
    """

    # Paths an unverified user is allowed to hit. Anything else redirects to
    # /verify/. Names resolve through reverse() at request time so URL-pattern
    # changes don't silently break the allow-list.
    _ALLOWED_URL_NAMES = (
        "identity-verification",  # /verify/ — the gate target itself
        "veriff-session",         # AJAX endpoint that creates the Veriff session
        "logout",
        "login",
        "register",
        "check-email",
        # Password-recovery routes stay reachable so a user who is logged in
        # but stuck unverified can still recover access if needed.
        "forgot-password",
        "verify-otp",
        "reset-password",
        # Public marketing pages reachable from the top navigation on the
        # /verify/ and /membership/ chrome. An unverified user must still be
        # able to browse Home / World Map / About / Careers / Contact —
        # otherwise every nav click bounces them back to /verify/. Verification
        # is still enforced for the app itself (membership, plan selection,
        # dashboard, apply), so this doesn't let anyone skip Veriff; it only
        # keeps the public pages public. Mirrors the same allow-list in
        # RequireCompanyForBusinessUserMiddleware.
        "home",
        "home_root",  # bare "/" serves the same home view as /home/
        "worldmap",
        "about",
        "career",
        "contact",
        "set_language",
    )

    # Prefixes always allowed: static/media assets keep loading, the admin
    # login flow is independent, and /veriff/ covers both the session API and
    # the decision webhook Veriff calls back into.
    _ALLOWED_PREFIXES = (
        "/static/",
        "/media/",
        "/admin/",
        "/veriff/",
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
                # URL not registered — happens during early app boot or in
                # test setups. Skip rather than crashing the whole stack.
                continue
        return paths

    def __call__(self, request):
        if not self._needs_redirect(request):
            return self.get_response(request)

        try:
            return redirect("identity-verification")
        except NoReverseMatch:
            return self.get_response(request)

    def _needs_redirect(self, request):
        # Local-testing escape hatch: when VERIFF_BYPASS is on, the gate is
        # disabled entirely so you can register/test on localhost without a
        # reachable Veriff webhook. Off by default; never enabled in prod.
        from django.conf import settings
        if getattr(settings, "VERIFF_BYPASS", False):
            return False

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        # Platform admin and tenant admins never go through Veriff.
        if user.is_superuser:
            return False
        role = getattr(user, "role", None)
        role_name = ((role.name or "") if role else "").lower()
        if role_name == "tenant_admin":
            return False

        # Submitted-or-approved — let them through (no waiting on the decision).
        if (user.verification_status or "") in GATE_PASS_STATUSES:
            return False

        path = request.path or ""

        # Honor the allow-list before bouncing.
        if path in self._allowed_paths:
            return False
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return False

        return True
