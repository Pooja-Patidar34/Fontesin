class NoCachePagesMiddleware:
    """
    Stop the browser from caching HTML pages so the back button always
    re-fetches.

    Without this, clicking Back after login surfaces a stale login form
    whose CSRF token no longer matches the current session — submitting it
    produces the 403 "CSRF verification failed" page. With this header set,
    Back triggers a fresh request: an authenticated user is bounced to the
    dashboard by `admin_login`, and a logged-out user is bounced to login
    by `@login_required`.

    Static and media URLs are skipped so versioned assets keep caching
    normally. JSON / file responses are skipped too — they're consumed by
    JS, not by the back button.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path or ""
        if path.startswith("/static/") or path.startswith("/media/"):
            return response

        ctype = response.get("Content-Type", "") or ""
        if "text/html" not in ctype:
            return response

        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
