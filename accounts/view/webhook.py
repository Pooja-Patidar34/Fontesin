# views.py

import base64
import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def veriff_webhook(request):

    if request.method == "POST":
        print("Received webhook from Veriff")
        signature = request.headers.get("X-HMAC-SIGNATURE")
        payload = request.body

        expected_signature = base64.b64encode(
            hmac.new(
                settings.VERIFF_WEBHOOK_SECRET.encode(),
                payload,
                hashlib.sha256
            ).digest()
        ).decode()

        if signature != expected_signature:
            return JsonResponse({"error": "Invalid signature"}, status=400)

        data = json.loads(payload)

        print("Webhook received:", data)

        status = data["verification"]["status"]
        session_id = data["verification"]["id"]

        print("Verification status:", status)
        print("Session ID:", session_id)

        return JsonResponse({"success": True})

    return JsonResponse({"error": "Invalid request"})