from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch


class ActiveCompanyMiddleware:
    """Resolve the Business User's currently-selected company for the request,
    and force a multi-company owner to pick one before acting.

    Plans are company-scoped, so almost every feature gate needs to know
    which company the user is "acting as" right now. A user who owns more than
    one company chooses one at login; the choice is stored in the session as
    `active_company_id`. This middleware reads that id, loads the company
    (only if the user still owns it), and stashes it as both
    `request.active_company` and `request.user._active_company` — the latter
    is what `billing.utils.resolve_active_company` reads so the plan resolver
    works even in code paths that only have the user object.

    When a Business User owns MORE THAN ONE company but has no valid selection
    in the session (bookmarked /dashboard/, navigated directly, or their
    previous selection went stale), the plan resolver would silently fall back
    to primary_company / the oldest company — quietly acting as the WRONG
    company. To close that gap this middleware redirects such users to the
    company picker on any non-infrastructural path until they choose one.
    A single-company owner never hits the picker (auto-resolved); a company-
    less user is handled by RequireCompanyForBusinessUserMiddleware instead.

    Runs after AuthenticationMiddleware so `request.user` is populated, and
    before the plan/verification gates that read the plan.
    """

    # Paths reachable WITHOUT a company selection: the picker itself (else we
    # loop), auth entry/exit, and static/infra prefixes. Everything else for a
    # multi-company BU with no selection redirects to the picker.
    _ALLOWED_URL_NAMES = (
        "select-company",
        "logout",
        "login",
        "set_language",
        # /jsi18n/ sits outside the /i18n/ prefix below — without this the JS
        # translation catalog is redirected to the picker on every gated page.
        "javascript-catalog",
    )
    _ALLOWED_PREFIXES = (
        "/static/",
        "/media/",
        "/admin/",
        "/veriff/",
        "/i18n/",
    )

    def __init__(self, get_response):
        self.get_response = get_response
        self._allowed_paths = set()
        for name in self._ALLOWED_URL_NAMES:
            try:
                self._allowed_paths.add(reverse(name))
            except NoReverseMatch:
                continue

    def __call__(self, request):
        request.active_company = None
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False) and not user.is_superuser:
            company_id = None
            try:
                company_id = request.session.get("active_company_id")
            except Exception:
                company_id = None

            if company_id:
                from accounts.models import Company
                company = Company.objects.filter(
                    id=company_id, owner_user=user
                ).first()
                if company is not None:
                    request.active_company = company
                    # Read by billing.utils.resolve_active_company.
                    user._active_company = company
                else:
                    # Stale/invalid selection (company deleted or no longer
                    # owned) — clear it so the resolver auto-selects instead.
                    try:
                        del request.session["active_company_id"]
                    except KeyError:
                        pass

            # No valid selection resolved above: force the picker for a
            # multi-company Business User so no request silently acts as the
            # wrong company.
            if request.active_company is None:
                redirect_response = self._maybe_force_picker(request, user)
                if redirect_response is not None:
                    return redirect_response

        return self.get_response(request)

    def _maybe_force_picker(self, request, user):
        role = getattr(user, "role", None)
        role_code = ((role.code or "") if role else "").lower()
        if role_code != "business_user":
            return None

        path = request.path or ""
        if path in self._allowed_paths:
            return None
        for prefix in self._ALLOWED_PREFIXES:
            if path.startswith(prefix):
                return None

        from accounts.models import Company
        # Owning >1 company is only reachable post-verification, so this never
        # pre-empts the identity-verification gate in practice.
        owned_count = Company.objects.filter(owner_user=user).count()
        if owned_count > 1:
            try:
                return redirect("select-company")
            except NoReverseMatch:
                return None
        return None
