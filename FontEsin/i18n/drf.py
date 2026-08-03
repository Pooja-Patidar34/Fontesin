"""DRF hooks ensuring API responses use the active request locale."""

from django.utils import translation

from FontEsin.middleware.locale import normalize_locale


class APILocaleMixin:
    """Re-apply Accept-Language for API views when no cookie override is set.

    ``LocaleMiddleware`` and ``UserLocaleMiddleware`` already activate the
    request locale. This mixin ensures unauthenticated or header-only API
    clients still receive translated ``message`` / ``error`` fields.
    """

    def initial(self, request, *args, **kwargs):
        from django.conf import settings

        # An authenticated user's locale is their profile setting (or an
        # explicit ?lang=), already activated by UserLocaleMiddleware. Deriving
        # one from Accept-Language here would silently override the preference
        # they chose — and `normalize_locale` falls back to English for any
        # code it doesn't know, so an unrelated browser header would drag a
        # German user's API responses back to English.
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            lang_param = request.GET.get("lang")
            if not cookie_lang and not lang_param:
                # Django's negotiation honours q-weights and settings.LANGUAGES.
                # The hand-rolled split took the FIRST entry whatever its weight,
                # so "zh;q=0.1, de;q=0.9" resolved to English instead of German.
                django_request = getattr(request, "_request", request)
                negotiated = normalize_locale(
                    translation.get_language_from_request(
                        django_request, check_path=False,
                    )
                )
                translation.activate(negotiated)
                request.LANGUAGE_CODE = negotiated
        super().initial(request, *args, **kwargs)
