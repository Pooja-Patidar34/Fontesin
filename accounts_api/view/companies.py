
# from uuid import UUID
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated
# from rest_framework import status
# from django.db import DatabaseError

# from accounts.models import (
#     Company,
#     UserRole,
#     Permission,
# )
# from accounts_api.serializers.company_serializers import CompanySerializer,CompanyCreateUpdateSerializer
# from accounts_api.utils import get_user_role,can_manage_company

# class CompanyListAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         user = request.user
#         try:
#             if user.is_superuser:
#                 companies = Company.objects.select_related("tenant")

#                 tenant_id = request.query_params.get("tenant_id")
#                 if tenant_id:
#                     try:
#                         UUID(tenant_id)
#                     except ValueError:
#                         return Response({"status": False,"message": "Invalid tenant_id"},
#                             status=status.HTTP_400_BAD_REQUEST
#                         )

#                     companies = companies.filter(tenant_id=tenant_id)

#                 serializer = CompanySerializer(companies, many=True)
#                 return Response({"status": True, "data": serializer.data},
#                     status=status.HTTP_200_OK
#                 )
#             if not user.tenant:
#                 return Response({"status": False,"message": "User tenant not configured"},
#                     status=status.HTTP_403_FORBIDDEN
#                 )

#             role = get_user_role(user)
#             if not role:
#                 return Response(
#                     {"status": False,"message": "User role not assigned"},
#                     status=status.HTTP_403_FORBIDDEN
#                 )

#             if role.name == "tenant_admin":
#                 companies = (
#                     Company.objects
#                     .filter(tenant=user.tenant)
#                     .select_related("tenant")
#                 )

#                 serializer = CompanySerializer(companies, many=True)
#                 return Response(
#                     {"status": True, "data": serializer.data},
#                     status=status.HTTP_200_OK
#                 )

#             if not role.permissions.filter(code="company.view").exists():
#                 return Response(
#                     {"status": False,"message": "Permission denied"},
#                     status=status.HTTP_403_FORBIDDEN
#                 )

#             companies = (
#                 Company.objects
#                 .filter(tenant=user.tenant)
#                 .select_related("tenant")
#             )

#             serializer = CompanySerializer(companies, many=True)
#             return Response(
#                 {"status": True, "data": serializer.data},
#                 status=status.HTTP_200_OK
#             )

#         except DatabaseError:
#             return Response(
#                 {"status": False,"message": "Database error while fetching companies"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#         except Exception:
#             return Response(
#                 {"status": False,"message": "Unable to fetch companies at the moment"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         user = request.user

#         if not can_manage_company(user):
#             return Response(
#                 {"status": False, "message": "Permission denied"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         data = request.data.copy()
#         if not user.is_superuser:
#             data["tenant"] = str(user.tenant.id)

#         serializer = CompanyCreateUpdateSerializer(
#             data=data,
#             context={"request": request}
#         )

#         try:
#             if serializer.is_valid():
#                 company = serializer.save()
#                 return Response(
#                     {"status": True,"data": CompanySerializer(company).data},
#                     status=status.HTTP_201_CREATED
#                 )

#             return Response(
#                 {"status": False, "errors": serializer.errors},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         except DatabaseError:
#             return Response(
#                 {"status": False, "message": "Database error while creating company"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#         except Exception:
#             return Response(
#                 {"status": False, "message": "Unable to create company"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

# class CompanyUpdateAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def put(self, request, company_id):
#         user = request.user

#         if not can_manage_company(user):
#             return Response(
#                 {"status": False, "message": "Permission denied"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         try:
#             company = Company.objects.select_related("tenant").get(id=company_id)
#         except Company.DoesNotExist:
#             return Response(
#                 {"status": False, "message": "Company not found"},
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         if not user.is_superuser and company.tenant != user.tenant:
#             return Response(
#                 {"status": False,"message": "You cannot modify a company outside your tenant"},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         serializer = CompanyCreateUpdateSerializer(
#             company,
#             data=request.data,
#             partial=True,
#             context={"request": request}
#         )

#         try:
#             if serializer.is_valid():
#                 company = serializer.save()
#                 return Response(
#                     {"status": True,"data": CompanySerializer(company).data},
#                     status=status.HTTP_200_OK
#                 )

#             return Response(
#                 {"status": False, "errors": serializer.errors},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         except DatabaseError:
#             return Response(
#                 {"status": False, "message": "Database error while updating company"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#         except Exception:
#             return Response(
#                 {"status": False, "message": "Unable to update company"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )



from uuid import UUID
from drf_spectacular.utils import (
    extend_schema,
    OpenApiParameter,
    OpenApiResponse,
)
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import DatabaseError

from accounts.models import Company
from accounts_api.serializers.company_serializers import (
    CompanySerializer,
    CompanyCreateUpdateSerializer,
)
from accounts_api.utils import get_user_role, can_manage_company


class CompanyListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List companies",
        description=(
            "Returns list of companies.\n\n"
            "- Superuser can view all companies (optionally filter by tenant)\n"
            "- Tenant admin can view companies under their tenant\n"
            "- Other users need `company.view` permission"
        ),
        parameters=[
            OpenApiParameter(
                name="tenant_id",
                description="Filter companies by tenant (UUID). Only for superusers.",
                required=False,
                type=str,
            )
        ],
        responses={
            200: CompanySerializer(many=True),
            400: OpenApiResponse(description="Invalid tenant_id"),
            403: OpenApiResponse(description="Permission denied"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["Companies"],
    )
    def get(self, request):
        user = request.user
        try:
            if user.is_superuser:
                companies = Company.objects.select_related("tenant")

                tenant_id = request.query_params.get("tenant_id")
                if tenant_id:
                    try:
                        UUID(tenant_id)
                    except ValueError:
                        return Response(
                            {"status": False, "message": "Invalid tenant_id"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    companies = companies.filter(tenant_id=tenant_id)

                serializer = CompanySerializer(companies, many=True)
                return Response({"status": True, "data": serializer.data})

            if not user.tenant:
                return Response(
                    {"status": False, "message": "User tenant not configured"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            role = get_user_role(user)
            if not role:
                return Response(
                    {"status": False, "message": "User role not assigned"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if role.name != "tenant_admin" and not role.permissions.filter(code="company.view").exists():
                return Response(
                    {"status": False, "message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            companies = Company.objects.filter(tenant=user.tenant)
            serializer = CompanySerializer(companies, many=True)
            return Response({"status": True, "data": serializer.data})

        except DatabaseError:
            return Response(
                {"status": False, "message": "Database error while fetching companies"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            return Response(
                {"status": False, "message": "Unable to fetch companies"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Create company",
        description="Create a new company. Tenant is auto-assigned for non-superusers.",
        request=CompanyCreateUpdateSerializer,
        responses={
            201: CompanySerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["Companies"],
    )
    def post(self, request):
        user = request.user

        if not can_manage_company(user):
            return Response(
                {"status": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        if not user.is_superuser:
            data["tenant"] = str(user.tenant.id)

        serializer = CompanyCreateUpdateSerializer(
            data=data, context={"request": request}
        )

        try:
            if serializer.is_valid():
                company = serializer.save()
                return Response(
                    {"status": True, "data": CompanySerializer(company).data},
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except DatabaseError:
            return Response(
                {"status": False, "message": "Database error while creating company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            return Response(
                {"status": False, "message": "Unable to create company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CompanyUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update company",
        description="Update company details (partial update allowed).",
        parameters=[
            OpenApiParameter(
                name="company_id",
                description="Company ID (UUID)",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
        request=CompanyCreateUpdateSerializer,
        responses={
            200: CompanySerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Company not found"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["Companies"],
    )
    def put(self, request, company_id):
        user = request.user

        if not can_manage_company(user):
            return Response(
                {"status": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"status": False, "message": "Company not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_superuser and company.tenant != user.tenant:
            return Response(
                {
                    "status": False,
                    "message": "You cannot modify a company outside your tenant",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CompanyCreateUpdateSerializer(
            company,
            data=request.data,
            partial=True,
            context={"request": request},
        )

        try:
            if serializer.is_valid():
                company = serializer.save()
                return Response(
                    {"status": True, "data": CompanySerializer(company).data}
                )

            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except DatabaseError:
            return Response(
                {"status": False, "message": "Database error while updating company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            return Response(
                {"status": False, "message": "Unable to update company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CompanyDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get company details",
        description=(
            "Retrieve full details of a company.\n\n"
            "- Superuser can view any company\n"
            "- Tenant admin can view companies in their tenant\n"
            "- Other users need `company.view` permission"
        ),
        parameters=[
            OpenApiParameter(
                name="company_id",
                description="Company ID (UUID)",
                required=True,
                type=str,
                location=OpenApiParameter.PATH,
            )
        ],
        responses={
            200: CompanyCreateUpdateSerializer,
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Company not found"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["Companies"],
    )
    def get(self, request, company_id):
        user = request.user

        try:
            # Fetch company
            company = Company.objects.select_related("tenant").get(id=company_id)

            # Tenant boundary
            if not user.is_superuser and company.tenant != user.tenant:
                return Response(
                    {"status": False, "message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # RBAC
            if not user.is_superuser:
                role = get_user_role(user)
                if not role:
                    return Response(
                        {"status": False, "message": "User role not assigned"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                if (
                    role.name != "tenant_admin"
                    and not role.permissions.filter(code="company.view").exists()
                ):
                    return Response(
                        {"status": False, "message": "Permission denied"},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            serializer = CompanyCreateUpdateSerializer(company)
            return Response(
                {"status": True, "data": serializer.data},
                status=status.HTTP_200_OK,
            )

        except Company.DoesNotExist:
            return Response(
                {"status": False, "message": "Company not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        except DatabaseError:
            return Response(
                {
                    "status": False,
                    "message": "Database error while fetching company details",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            return Response(
                {
                    "status": False,
                    "message": "Unable to fetch company details",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )