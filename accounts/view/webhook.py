import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger("technical")


@csrf_exempt
def veriff_webhook(request):

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=405)

    logger.info("Received webhook from Veriff")

    signature = request.headers.get("X-HMAC-SIGNATURE")

    if not signature:
        return JsonResponse({"error": "Missing signature"}, status=400)

    payload = request.body

    expected_signature = hmac.new(
        settings.VERIFF_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if signature != expected_signature:
        logger.warning("Invalid Veriff webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    data = json.loads(payload)

    logger.info("Webhook verified successfully")
    logger.debug("Webhook payload: %s", data)

    # EVENT WEBHOOK (submitted, started etc.)
    if "action" in data:

        action = data.get("action")
        session_id = data.get("id")
        vendor_data = data.get("vendorData")

        logger.info("Event webhook received - Action: %s, Session: %s, VendorData: %s", action, session_id, vendor_data)

        return JsonResponse({"success": True})


    # DECISION WEBHOOK (approved / declined)
    if "verification" in data:

        verification = data["verification"]

        session_id = verification.get("id")
        verification_status = verification.get("status")
        vendor_data = verification.get("vendorData")

        logger.info("Decision webhook received - Session: %s, Status: %s, VendorData: %s", session_id, verification_status, vendor_data)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=vendor_data)
            user.verification_status = verification_status
            user.save(update_fields=["verification_status"])
            logger.info("User %s verification updated to %s", vendor_data, verification_status)

        except User.DoesNotExist:
            logger.error("User not found for vendor_data: %s", vendor_data)

        return JsonResponse({"success": True})


    return JsonResponse({"success": True})