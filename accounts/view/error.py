from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _


def error_403(request, exception=None):
    return render(request, "403.html", status=403)


def csrf_failure(request, reason="", template_name=None):
    """Graceful handler for a failed CSRF check (wired via CSRF_FAILURE_VIEW).

    A stale form or a session/token that rotated out from under the page — e.g.
    re-logging-in as a different user in the same browser, then submitting a
    form that was rendered under the old session — makes the CSRF token
    mismatch. Django's default response is a bare "403 Forbidden" page, which
    reads as "Access Denied" and hides the real, recoverable cause. We DON'T run
    the action (the token check still failed); we just bounce the user back to
    where they were with a clear, retry-able message so they resubmit with a
    fresh token. AJAX/JSON callers get a machine-readable 403 instead.
    """
    accept = request.headers.get("accept", "")
    wants_json = (
        request.path.startswith("/api/")
        or request.headers.get("x-requested-with") == "XMLHttpRequest"
        or ("application/json" in accept and "text/html" not in accept)
    )
    text = _(
        "Your session or the form expired before it could be submitted. "
        "Please try again."
    )
    if wants_json:
        return JsonResponse({"error": text}, status=403)

    messages.error(request, text)
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    # No safe referer to return to — send an authenticated user to their
    # dashboard, otherwise to login (a fresh page carries a valid token).
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def error_404(request, exception=None):
    return render(request, "404.html", status=404)


def error_500(request):
    return render(request, "500.html", status=500)


def access_denied(request):
    return render(request, "403.html", status=403)