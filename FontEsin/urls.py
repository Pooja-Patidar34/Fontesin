from django.contrib import admin
from django.urls import path,include
from accounts.view.error import error_403
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    # path('admin/', admin.site.urls),
    # path('admin/', include('accounts.urls')),
    
    path("", include("accounts.urls")),
    path("api/", include("accounts_api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

handler403 = "accounts.view.error.error_403"

