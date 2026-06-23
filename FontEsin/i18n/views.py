"""Locale views extending Django's built-in i18n endpoints."""

from django.views.i18n import LANGUAGE_QUERY_PARAMETER, set_language as django_set_language

from accounts.constants import SupportedLocale
from FontEsin.middleware.locale import normalize_locale


def set_language(request):
    """Set language cookie and persist preference for authenticated users."""
    if request.method == "POST":
        lang_code = request.POST.get(LANGUAGE_QUERY_PARAMETER)
        if lang_code:
            language = normalize_locale(lang_code)
            if language in SupportedLocale.ALL:
                user = getattr(request, "user", None)
                if user and user.is_authenticated:
                    user.persist_preferred_language(language)

    return django_set_language(request)
