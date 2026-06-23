"""Shared i18n helpers for FONTESIN."""

from django.utils import translation

from accounts.constants import SupportedLocale
from FontEsin.middleware.locale import normalize_locale


def user_language(user) -> str:
    """Resolve a user's preferred locale, falling back to English."""
    if not user:
        return SupportedLocale.EN
    if hasattr(user, "effective_preferred_language"):
        return user.effective_preferred_language
    preferred = getattr(user, "preferred_language", None)
    return normalize_locale(preferred) if preferred else SupportedLocale.EN


def activate_user_language(user):
    """Activate gettext for a specific user (e.g. notification recipient)."""
    lang = user_language(user)
    translation.activate(lang)
    return lang
