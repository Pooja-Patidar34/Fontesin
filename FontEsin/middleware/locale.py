from django.conf import settings
from django.utils import translation

from accounts.constants import SupportedLocale


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


class UserLocaleMiddleware:
    """
    Resolve locale after authentication.

    Priority:
      1. Explicit ?lang= query parameter
      2. Authenticated user.preferred_language
      3. django_language cookie (set by the language switcher)
      4. Locale already activated by LocaleMiddleware (Accept-Language)
      5. English fallback for unsupported codes
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language, set_cookie = self._resolve_language(request)
        translation.activate(language)
        request.LANGUAGE_CODE = language

        response = self.get_response(request)

        if set_cookie:
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
            preferred = getattr(user, "preferred_language", None)
            if preferred:
                return normalize_locale(preferred), False

        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie_lang:
            return normalize_locale(cookie_lang), False

        activated = translation.get_language()
        if activated:
            return normalize_locale(activated), False

        return SupportedLocale.EN, False
