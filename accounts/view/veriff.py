import logging

import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework import status

logger = logging.getLogger("technical")


class CreateVeriffSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request):

        payload = {
            "verification": {
                "vendorData": str(request.user.id),
                "callback": settings.VERIFF_CALLBACK_URL,
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

        sessions_url = settings.VERIFF_BASE_URL.rstrip("/") + "/v1/sessions"

        try:

            response = requests.post(
                sessions_url,
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

            veriff_status = None
            veriff_body = None
            if getattr(e, "response", None) is not None:
                veriff_status = e.response.status_code
                try:
                    veriff_body = e.response.json()
                except ValueError:
                    veriff_body = e.response.text

            logger.error(
                "Veriff session creation failed: status=%s body=%s exc=%s",
                veriff_status, veriff_body, str(e),
            )

            return Response(
                {
                    "error": "Unable to create verification session",
                    "veriff_status": veriff_status,
                    "veriff_body": veriff_body,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )