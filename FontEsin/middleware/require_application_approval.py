from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


# Roles that must complete the apply form after Veriff before reaching the
# dashboard.
APPLY_REQUIRED_ROLE_CODES = ("consultant", "coordinator", "franchise")

# Of those, the roles that ALSO need super-admin approval before they get
# access. All three staff roles now submit a region selection AND wait for the
# super admin to approve/decline before they reach the dashboard. (Existing
# consultants were grandfathered to "approved" in migration 0043 so the new
# gate never locks out already-onboarded consultants.)
GATED_ROLE_CODES = ("consultant", "coordinator", "franchise")

# application_status that grants full access. Everything else keeps the
# account on the apply form / pending-review screen.
APPROVED_STATUS = "approved"


class RequireApplicationApprovalMiddleware:
    """Hold coordinator / franchise accounts out of the app until a super admin
    approves their application.

    Flow: register (role coordinator/franchise) → Veriff → /apply/ form →
    submit (application_status="submitted") → this gate shows the
    "application under review" page → super admin approves
    (application_status="approved") → full access. A declined application keeps
    them on the pending page with the decline reason.

    Runs AFTER RequireIdentityVerificationMiddleware (so Veriff is enforced
    first) and after the plan gate. Skips superusers, tenant admins, anyone who
    isn't a gated role, and accounts already approved. Existing staff were
    grandfathered to "approved" in migration 0039 so they're never caught here.
    """

    # Paths a not-yet-approved gated user may still reach: the apply flow, the
    # pending page, the Veriff step, auth, and public marketing pages. Anything
    # else redirects to the apply form (if they haven't submitted) or the
    # pending page (if they have).
    _ALLOWED_URL_NAMES = (
        "apply",
        "apply-submit",
        "apply-review",
        "application-pending",
        "identity-verification",
        "logout",
        "login",
        "register",
        "check-email",
        "forgot-password",
        "verify-otp",
        "reset-password",
        # Public marketing pages reachable from the page chrome.
        "home",
        "home_root",
        "worldmap",
        "about",
        "career",
        "contact",
        "set_language",
        # JS translation catalog (/jsi18n/) — no prefix covers it.
        "javascript-catalog",
    )

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
                continue
        return paths

    def __call__(self, request):
        target = self._redirect_target(request)
        if target is None:
            return self.get_response(request)
        try:
            return redirect(target)
        except NoReverseMatch:
            return self.get_response(request)

    def _redirect_target(self, request):
        """Return a URL name to redirect to, or None to let the request through."""
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        if user.is_superuser:
            return None

        role = getattr(user, "role", None)
        role_code = ((role.code or "") if role else "").lower()
        role_name = ((role.name or "") if role else "").lower()
        if role_name == "tenant_admin":
            return None
        if role_code not in APPLY_REQUIRED_ROLE_CODES:
            return None

        status = (user.application_status or "")
        needs_approval = role_code in GATED_ROLE_CODES

        # Full access once approved. (All apply-required roles now need
        # approval, so a bare "submitted" no longer grants access — the
        # not-needs-approval branch is kept only as a defensive fallback for
        # any future role that submits without requiring review.)
        if status == APPROVED_STATUS:
            return None
        if not needs_approval and status == "submitted":
            return None

        path = request.path or ""
        if path in self._allowed_paths:
            return None
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return None

        # Still gated. Coordinator/franchise who've already submitted (or were
        # declined) wait on the pending-review page; everyone else who hasn't
        # finished the apply form is sent to complete it.
        if needs_approval and status in ("submitted", "declined"):
            return "application-pending"
        return "apply"
