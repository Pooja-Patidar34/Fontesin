class ActiveCompanyMiddleware:
    """Resolve the Business User's currently-selected company for the request.

    Plans are company-scoped, so almost every feature gate needs to know
    which company the user is "acting as" right now. A user who owns more than
    one company chooses one at login; the choice is stored in the session as
    `active_company_id`. This middleware reads that id, loads the company
    (only if the user still owns it), and stashes it as both
    `request.active_company` and `request.user._active_company` — the latter
    is what `billing.utils.resolve_active_company` reads so the plan resolver
    works even in code paths that only have the user object.

    When no valid selection is present the attributes are left unset and the
    resolver falls back to auto-selecting a single owned company (or the
    primary_company). Runs after AuthenticationMiddleware so `request.user`
    is populated, and before the plan/verification gates that read the plan.
    """

    def __init__(self, get_response):
        self.get_response = get_response

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

        return self.get_response(request)
