from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from accounts_api.view.profile import UserProfileAPIView
from accounts_api.view.companies import (
    CompanyUpdateAPIView,
    CompanyListAPIView,
    CompanyDetailAPIView,
)
from accounts_api.view.industry_codes import (
    NaceCodeListAPIView,
    NaicsCodeListAPIView,
)

urlpatterns = [
    path("login/", TokenObtainPairView.as_view()),
    path("refresh/", TokenRefreshView.as_view()),
    path("profile/", UserProfileAPIView.as_view()),
    path("companies/", CompanyListAPIView.as_view()),
    path("companies/<uuid:company_id>/", CompanyUpdateAPIView.as_view(), name="company-update"),
    path("companies/<uuid:company_id>/detail/", CompanyDetailAPIView.as_view(), name="api-company-detail"),
    path("industry-codes/nace/", NaceCodeListAPIView.as_view(), name="api-industry-codes-nace"),
    path("industry-codes/naics/", NaicsCodeListAPIView.as_view(), name="api-industry-codes-naics"),
]


