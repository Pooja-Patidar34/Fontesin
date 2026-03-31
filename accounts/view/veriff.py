import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework import status


class CreateVeriffSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):

        payload = {
            "verification": {
                "vendorData": str(request.user.id),
                "callback": "https://960f-2401-4900-8820-177e-cc75-6884-ef7a-4eab.ngrok-free.app/membership/",
                "person": {
                    "firstName": request.user.first_name or "Test",
                    "lastName": request.user.last_name or "User",
                }
            }
        }

        headers = {
            "X-AUTH-CLIENT": settings.VERIFF_API_KEY,
            "Content-Type": "application/json"
        }

        try:

            response = requests.post(
                "https://stationapi.veriff.com/v1/sessions",
                json=payload,
                headers=headers,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

            session_id = data["verification"]["id"]

            if request.user.is_authenticated:
                request.user.veriff_session_id = session_id
                request.user.save()

            return Response({
                "session_url": data["verification"]["url"],
                "session_id": session_id
            })

        except requests.exceptions.RequestException as e:

            print("VERIFF ERROR:", str(e))

            return Response(
                {"error": "Unable to create verification session"},
                status=status.HTTP_400_BAD_REQUEST
            )