from django.contrib import admin
from django.urls import path,include
from accounts.view.error import error_403
urlpatterns = [
    # path('admin/', admin.site.urls),
    # path('admin/', include('accounts.urls')),
    
    path(
        "admin/",
        include(("accounts.urls", "admin"), namespace="admin")
    ),
]

handler403 = "accounts.view.error.error_403"