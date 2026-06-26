from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class RequirePlanForBusinessUserMiddleware:
    """
    Force business users without an active/pending subscription onto the
    membership page until they pick a plan.

    The login view already redirects them to /membership/ once, but a user
    could navigate elsewhere via the back button or by typing a URL. This
    middleware closes that gap — every request from an unsubscribed business
    user is bounced to membership, except for the small allow-list of paths
    they need to select a plan, log out, or load static assets.

    Skipped roles: superusers, tenant admins, consultants, coordinators,
    franchises — none of them buy plans, so we don't gate them.
    """

    # Paths an unsubscribed business user is allowed to hit. Anything else
    # redirects to /membership/. Names map through reverse() at request time
    # so URL-pattern changes don't break the allow-list.
    #
    # `identity-verification` (= /verify/) is critical: register_view sends
    # every freshly-registered user there to run Veriff KYC *before* they
    # ever see /membership/. Without this entry the middleware intercepts
    # the post-registration redirect and bounces business users straight
    # to /membership/, silently skipping the identity check.
    _ALLOWED_URL_NAMES = (
        "membership",
        "select_plan",
        "logout",
        "login",
        "register",
        "identity-verification",
        "verify-otp",
        "forgot-password",
        "reset-password",
        "check-email",
        # Public marketing pages reachable from the top navigation. These
        # are linked from the registration/membership chrome itself, so an
        # unsubscribed business user must be able to browse them — otherwise
        # every nav click (Home / World Map / About / Careers / Contact)
        # gets bounced straight back to /membership/.
        "home",
        "home_root",  # bare "/" serves the same home view as /home/
        "worldmap",
        "about",
        "career",
        "contact",
        "set_language",
    )

    # Path prefixes always allowed (static, admin login flow, identity
    # verification redirect targets). Static/media keep loading; the Veriff
    # callback may land here while the user hasn't picked a plan yet.
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
            return redirect("membership")
        except NoReverseMatch:
            return self.get_response(request)

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

        # Honor the allow-list before doing any DB work.
        if path in self._allowed_paths:
            return False
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return False

        # Lazy import — avoids circular imports during Django app loading,
        # since this middleware is wired up before billing's app registry
        # is fully populated.
        from billing.models import Subscription
        has_sub = Subscription.objects.filter(
            user=user, status__in=("active", "trial", "created")
        ).exists()
        return not has_sub
