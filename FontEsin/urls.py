from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.i18n import JavaScriptCatalog

from FontEsin.i18n.views import set_language
from accounts.view.error import error_403, error_404, error_500
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # path('admin/', admin.site.urls),
    # path('admin/', include('accounts.urls')),

    path("i18n/setlang/", set_language, name="set_language"),
    path("jsi18n/", JavaScriptCatalog.as_view(packages=["FontEsin"]), name="javascript-catalog"),
    path("", include("accounts.urls")),
    path("api/", include("accounts_api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/listings/", include('listings.urls')),
    path("listings/", include('listings.web_urls')),
    path("modules/", include('listings.module_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "accounts.view.error.error_403"
handler404 = "accounts.view.error.error_404"
handler500 = "accounts.view.error.error_500"

