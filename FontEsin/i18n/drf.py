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

        cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        lang_param = request.GET.get("lang")
        if not cookie_lang and not lang_param:
            accept = request.headers.get("Accept-Language", "")
            for part in accept.split(","):
                code = part.split(";")[0].strip()
                normalized = normalize_locale(code)
                if normalized:
                    translation.activate(normalized)
                    request.LANGUAGE_CODE = normalized
                    break
        super().initial(request, *args, **kwargs)
