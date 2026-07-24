from django.urls import path

from listings import web

app_name = "modules"

urlpatterns = [
    path("", web.modules_dashboard, name="dashboard"),
    path("<slug:slug>/", web.module_landing, name="landing"),
]
