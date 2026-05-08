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

        verification = {
            "vendorData": str(request.user.id),
            "person": {
                "firstName": request.user.first_name or "Test",
                "lastName": request.user.last_name or "User",
            },
        }

        # Veriff's WAF rejects sessions with non-domain callbacks (bare IPs,
        # localhost, etc.) on live integrations, so only include the field
        # when it points at a real hostname.
        callback_url = (settings.VERIFF_CALLBACK_URL or "").strip()
        if callback_url:
            from urllib.parse import urlparse
            host = urlparse(callback_url).hostname or ""
            looks_like_ip = host.replace(".", "").isdigit()
            looks_like_local = host in ("localhost", "127.0.0.1", "0.0.0.0")
            if host and not looks_like_ip and not looks_like_local:
                verification["callback"] = callback_url

        payload = {"verification": verification}

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