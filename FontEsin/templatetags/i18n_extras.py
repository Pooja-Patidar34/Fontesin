from django import template
from django.conf import settings
from django.utils.translation import get_language

from accounts.constants import SupportedLocale
from accounts.role_i18n import localized_role_label
from FontEsin.middleware.locale import normalize_locale

register = template.Library()

LANGUAGE_DISPLAY_NAMES = {
    SupportedLocale.EN: "English",
    SupportedLocale.DE: "Deutsch",
    SupportedLocale.ES: "Español",
    SupportedLocale.FR: "Français",
}


def _active_language(request):
    """Resolve the language code shown in the header switcher."""
    # The locale the request is actually rendering in — UserLocaleMiddleware
    # already resolved it (?lang= wins over the profile preference), so reading
    # effective_preferred_language here would show the profile language while
    # the page around it renders in the one from ?lang=.
    return normalize_locale(getattr(request, "LANGUAGE_CODE", None) or get_language())


@register.inclusion_tag("partials/_language_switcher.html", takes_context=True)
def language_switcher(context):
    request = context["request"]
    current = _active_language(request)
    languages = [
        {
            "code": code,
            "abbr": code.upper(),
            "label": LANGUAGE_DISPLAY_NAMES.get(code, label),
        }
        for code, label in settings.LANGUAGES
    ]
    return {
        "request": request,
        "current_language": current,
        "current_abbr": current.upper(),
        "languages": languages,
    }


@register.simple_tag
def active_locale():
    return get_language() or SupportedLocale.EN


@register.filter
def localized_role_label_filter(user):
    return localized_role_label(user)
