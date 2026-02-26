from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import DatabaseError
from django.db.models import Prefetch

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
)

from accounts.models import User, UserCompany
from accounts_api.serializers.profile_serializers import UserProfileSerializer


class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get logged-in user profile",
        description=(
            "Returns the complete profile of the currently authenticated user.\n\n"
            "**Includes:**\n"
            "- Basic user details\n"
            "- Tenant ID\n"
            "- Role name\n"
            "- Contact & address info\n"
            "- List of companies linked to the user\n\n"
            "**Authentication:** Bearer JWT token required."
        ),
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(description="Authentication credentials were not provided"),
            404: OpenApiResponse(description="User not found"),
            500: OpenApiResponse(description="Server error"),
        },
        tags=["Profile"],
    )
    def get(self, request):
        try:
            user = (
                User.objects
                .select_related("tenant", "role")
                .prefetch_related(
                    Prefetch(
                        "usercompany_set",
                        queryset=UserCompany.objects.select_related("company"),
                    )
                )
                .get(id=request.user.id)
            )

            serializer = UserProfileSerializer(user)
            return Response(
                {
                    "status": True,
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "User not found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except DatabaseError:
            return Response(
                {
                    "status": False,
                    "message": "Database error while fetching profile",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            return Response(
                {
                    "status": False,
                    "message": "Unable to fetch profile at the moment",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )