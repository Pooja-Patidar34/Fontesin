
from uuid import UUID
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import DatabaseError

from accounts.models import (
    Company,
    UserRole,
    Permission,
)
from accounts_api.serializers.company_serializers import CompanySerializer,CompanyCreateUpdateSerializer
from accounts_api.utils import get_user_role,can_manage_company

class CompanyListAPIView(APIView):
    permission_classes = [IsAuthenticated]

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
                        return Response({"status": False,"message": "Invalid tenant_id"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    companies = companies.filter(tenant_id=tenant_id)

                serializer = CompanySerializer(companies, many=True)
                return Response({"status": True, "data": serializer.data},
                    status=status.HTTP_200_OK
                )
            if not user.tenant:
                return Response({"status": False,"message": "User tenant not configured"},
                    status=status.HTTP_403_FORBIDDEN
                )

            role = get_user_role(user)
            if not role:
                return Response(
                    {"status": False,"message": "User role not assigned"},
                    status=status.HTTP_403_FORBIDDEN
                )

            if role.name == "tenant_admin":
                companies = (
                    Company.objects
                    .filter(tenant=user.tenant)
                    .select_related("tenant")
                )

                serializer = CompanySerializer(companies, many=True)
                return Response(
                    {"status": True, "data": serializer.data},
                    status=status.HTTP_200_OK
                )

            if not role.permissions.filter(code="company.view").exists():
                return Response(
                    {"status": False,"message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN
                )

            companies = (
                Company.objects
                .filter(tenant=user.tenant)
                .select_related("tenant")
            )

            serializer = CompanySerializer(companies, many=True)
            return Response(
                {"status": True, "data": serializer.data},
                status=status.HTTP_200_OK
            )

        except DatabaseError:
            return Response(
                {"status": False,"message": "Database error while fetching companies"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception:
            return Response(
                {"status": False,"message": "Unable to fetch companies at the moment"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not can_manage_company(user):
            return Response(
                {"status": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        if not user.is_superuser:
            data["tenant"] = str(user.tenant.id)

        serializer = CompanyCreateUpdateSerializer(
            data=data,
            context={"request": request}
        )

        try:
            if serializer.is_valid():
                company = serializer.save()
                return Response(
                    {"status": True,"data": CompanySerializer(company).data},
                    status=status.HTTP_201_CREATED
                )

            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except DatabaseError:
            return Response(
                {"status": False, "message": "Database error while creating company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception:
            return Response(
                {"status": False, "message": "Unable to create company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CompanyUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, company_id):
        user = request.user

        if not can_manage_company(user):
            return Response(
                {"status": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            company = Company.objects.select_related("tenant").get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"status": False, "message": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.is_superuser and company.tenant != user.tenant:
            return Response(
                {"status": False,"message": "You cannot modify a company outside your tenant"},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CompanyCreateUpdateSerializer(
            company,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        try:
            if serializer.is_valid():
                company = serializer.save()
                return Response(
                    {"status": True,"data": CompanySerializer(company).data},
                    status=status.HTTP_200_OK
                )

            return Response(
                {"status": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        except DatabaseError:
            return Response(
                {"status": False, "message": "Database error while updating company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception:
            return Response(
                {"status": False, "message": "Unable to update company"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
