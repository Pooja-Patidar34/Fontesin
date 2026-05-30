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
        #
        # Prefer the CURRENT request's host (so prod traffic redirects back
        # to the prod domain, dev to dev, etc.) and fall back to the env-var
        # callback only if the dynamic host can't be used. Without this, a
        # stale VERIFF_CALLBACK_URL pinned to a dead host would dead-end
        # every verification — which is exactly the bug we hit when the old
        # staging IP went away.
        from urllib.parse import urlparse

        def _is_acceptable_host(host_value):
            if not host_value:
                return False
            if host_value in ("localhost", "127.0.0.1", "0.0.0.0"):
                return False
            # Bare-IP detection: strip dots and check it's all digits
            # (covers IPv4 like "52.53.204.127"). We do NOT reject
            # IP-as-DNS wrappers like "*.nip.io" because they parse as
            # real domains — Veriff accepts them.
            if host_value.replace(".", "").isdigit():
                return False
            return True

        callback_url = ""
        # Build from the live request first so a stale env-var override
        # can't strand users on a dead host.
        request_callback = request.build_absolute_uri("/membership/")
        if _is_acceptable_host(urlparse(request_callback).hostname):
            callback_url = request_callback
        else:
            # Local dev / direct-IP traffic — fall back to the configured
            # production callback if it's a real domain.
            env_callback = (settings.VERIFF_CALLBACK_URL or "").strip()
            if env_callback and _is_acceptable_host(urlparse(env_callback).hostname):
                callback_url = env_callback

        if callback_url:
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