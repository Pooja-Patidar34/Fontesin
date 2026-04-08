# views.py
import hashlib
import hmac
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt



@csrf_exempt
def veriff_webhook(request):

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=405)

    print("Received webhook from Veriff")

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
        print("Invalid signature")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    data = json.loads(payload)

    print("Webhook verified successfully")
    print("Webhook payload:", data)

    # EVENT WEBHOOK (submitted, started etc.)
    if "action" in data:

        action = data.get("action")
        session_id = data.get("id")
        vendor_data = data.get("vendorData")

        print("Event webhook received")
        print("Action:", action)
        print("Session ID:", session_id)
        print("VendorData:", vendor_data)

        return JsonResponse({"success": True})


    # DECISION WEBHOOK (approved / declined)
    if "verification" in data:

        verification = data["verification"]

        session_id = verification.get("id")
        verification_status = verification.get("status")
        vendor_data = verification.get("vendorData")

        print("Decision webhook received")
        print("Session ID:", session_id)
        print("Status:", verification_status)
        print("VendorData:", vendor_data)

        # Example DB update logic
        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=vendor_data)

            user.verification_status = verification_status
            user.save()

            print("User verification updated successfully")

        except User.DoesNotExist:
            print("User not found:", vendor_data)

        return JsonResponse({"success": True})


    return JsonResponse({"success": True})