import hashlib
import hmac
import logging

import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework import status

logger = logging.getLogger("technical")


def sync_veriff_decision(user):
    """Pull the latest decision for the user's Veriff session straight from
    Veriff's API and persist it to user.verification_status.

    The registration gate normally learns the outcome from the async decision
    webhook (accounts/view/webhook.py). But the webhook can be delayed, or
    unreachable entirely (local dev / IP-only hosts Veriff can't call back
    into), which strands a freshly-verified user on the /verify/ step — they
    complete Veriff, get bounced back, and the status is still "pending".
    Polling the decision endpoint on return closes that gap so approval doesn't
    depend on the webhook landing first.

    Returns the refreshed status string (e.g. "approved"), or None when there's
    no session yet or Veriff has no decision / the call fails. Never raises —
    callers can treat None as "no change".
    """
    session_id = (getattr(user, "veriff_session_id", "") or "").strip()
    if not session_id:
        return None

    # Veriff signs API reads with HMAC-SHA256 of the session id using the
    # integration's shared secret (same secret family as the webhook). Try the
    # master secret first, then fall back to the webhook secret in case the
    # deployment only set one of the two.
    secret = (getattr(settings, "VERIFF_MASTER_SECRET", "") or
              getattr(settings, "VERIFF_WEBHOOK_SECRET", "") or "")
    if not secret:
        return None

    signature = hmac.new(
        secret.encode(), session_id.encode(), hashlib.sha256
    ).hexdigest()

    url = settings.VERIFF_BASE_URL.rstrip("/") + f"/v1/sessions/{session_id}/decision"
    headers = {
        "X-AUTH-CLIENT": settings.VERIFF_API_KEY,
        "X-HMAC-SIGNATURE": signature,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("Veriff decision poll failed for session %s: %s", session_id, e)
        return None

    verification = (data or {}).get("verification")
    if not verification:
        # No decision recorded yet (still processing) — leave status untouched.
        return None

    new_status = verification.get("status")
    if new_status and new_status != (user.verification_status or ""):
        user.verification_status = new_status
        user.save(update_fields=["verification_status"])
        logger.info(
            "User %s verification synced to %s via decision poll",
            user.id, new_status,
        )
    return new_status


class VeriffStatusAPIView(APIView):
    """Lightweight polling endpoint for the "Verifying your identity…" screen.

    The /verify/ page hits this every few seconds after the user returns from
    Veriff. It pulls the latest decision straight from Veriff
    (sync_veriff_decision) and reports back so the page can auto-forward to plan
    selection the moment the decision lands — instead of leaving the user on
    the verification step waiting on the async webhook.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from FontEsin.middleware.require_verification import VERIFIED_STATUSES

        current = request.user.verification_status or ""
        # Only bother Veriff while we're still waiting on a decision.
        if current not in VERIFIED_STATUSES:
            synced = sync_veriff_decision(request.user)
            if synced:
                current = synced

        # Statuses that mean the user must re-attempt rather than keep waiting.
        FAILED = ("declined", "resubmission_requested", "expired", "abandoned")
        approved = current in VERIFIED_STATUSES
        return Response({
            "status": current,
            "approved": approved,
            "failed": (current in FAILED),
            "pending": (not approved and current not in FAILED),
        })


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