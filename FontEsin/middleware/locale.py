from django.conf import settings
from django.utils import translation

from accounts.constants import SupportedLocale


# Django 5.x persists language in a cookie only; we mirror the choice in the
# session as well so anonymous users keep their locale across navigation.
LANGUAGE_SESSION_KEY = "_language"


def normalize_locale(code):
    """Map a locale code to a supported locale; unknown values fall back to English."""
    if not code:
        return SupportedLocale.EN
    base = str(code).split("-")[0].lower()
    if base in SupportedLocale.ALL:
        return base
    return SupportedLocale.EN


def apply_language_cookie(response, language):
    """Set the django_language cookie on a response."""
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


def sync_language_storage(request, response, language):
    """Keep Django's session key and language cookie aligned with the active locale."""
    if hasattr(request, "session"):
        request.session[LANGUAGE_SESSION_KEY] = language
    apply_language_cookie(response, language)
    return response


class UserLocaleMiddleware:
    """
    Resolve locale after authentication.

    Authenticated users:
      1. Explicit ?lang= query parameter
      2. user.preferred_language (falls back to English when unset)
      3. Sync session + cookie to match the profile language

    Anonymous users:
      1. Explicit ?lang= query parameter
      2. django_language session key (set by Django's set_language view)
      3. django_language cookie
      4. English fallback
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language, sync_storage = self._resolve_language(request)
        translation.activate(language)
        request.LANGUAGE_CODE = language

        if sync_storage and hasattr(request, "session"):
            request.session[LANGUAGE_SESSION_KEY] = language

        response = self.get_response(request)

        if sync_storage:
            apply_language_cookie(response, language)

        if hasattr(response, "headers"):
            response.headers["Content-Language"] = language
        else:
            response["Content-Language"] = language

        return response

    def _resolve_language(self, request):
        lang_param = request.GET.get("lang")
        if lang_param:
            return normalize_locale(lang_param), True

        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            return user.effective_preferred_language, True

        if hasattr(request, "session"):
            session_lang = request.session.get(LANGUAGE_SESSION_KEY)
            if session_lang:
                return normalize_locale(session_lang), False

        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang:
            return normalize_locale(cookie_lang), False

        return SupportedLocale.EN, False
