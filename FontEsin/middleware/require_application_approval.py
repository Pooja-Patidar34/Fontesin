from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


# Roles whose registration must be approved by a super admin before they can
# use the dashboard. Consultants are intentionally NOT gated.
GATED_ROLE_CODES = ("coordinator", "franchise")

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
        if role_code not in GATED_ROLE_CODES:
            return None

        # Approved → full access.
        if (user.application_status or "") == APPROVED_STATUS:
            return None

        path = request.path or ""
        if path in self._allowed_paths:
            return None
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return None

        # Not approved and trying to reach a gated page. If they've already
        # submitted (or been declined), send them to the pending/review page;
        # otherwise send them to the apply form to complete their application.
        if (user.application_status or "") in ("submitted", "declined"):
            return "application-pending"
        return "apply"
