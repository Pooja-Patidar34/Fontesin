from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Prefetch

from accounts.models import (
    User,
    UserCompany,
    UserCompanyRole,
)
from accounts_api.serializers.profile_serializers import UserProfileSerializer



class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = (
                User.objects
                .select_related("tenant", "primary_company")
                .get(id=request.user.id, is_active=True)
            )

            serializer = UserProfileSerializer(user)
            return Response(
                {
                    "status": True,
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response(
                {
                    "status": False,
                    "message": "User not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as exc:
            return Response(
                {
                    "status": False,
                    "message": "Unable to fetch profile at the moment"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
