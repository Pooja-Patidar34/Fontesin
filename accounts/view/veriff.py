# import requests
# from django.conf import settings
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework.permissions import IsAuthenticated,AllowAny
# from rest_framework import status


# class CreateVeriffSessionAPIView(APIView):

#     permission_classes = [AllowAny]

#     def get(self, request):

#         payload = {
#             "verification": {
#                 "callback": settings.VERIFF_WEBHOOK_URL,
#                 "person": {
#                     "firstName": request.user.first_name,
#                     "lastName": request.user.last_name
#                 }
#             }
#         }

#         headers = {
#             "X-AUTH-CLIENT": settings.VERIFF_API_KEY,
#             "Content-Type": "application/json"
#         }

#         try:

#             response = requests.post(
#                 f"{settings.VERIFF_BASE_URL}/v1/sessions",
#                 json=payload,
#                 headers=headers,
#                 timeout=10
#             )

#             response.raise_for_status()

#             data = response.json()

#             return Response({
#                 "session_url": data["verification"]["url"]
#             })

#         except requests.exceptions.RequestException as e:

#             return Response(
#                 {"error": "Unable to create verification session"},
#                 status=status.HTTP_400_BAD_REQUEST
#             )


import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status


class CreateVeriffSessionAPIView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):

        payload = {
            "verification": {
                "person": {
                    "firstName": (
                        request.user.first_name
                        if request.user.is_authenticated
                        else "Test"
                    ),
                    "lastName": (
                        request.user.last_name
                        if request.user.is_authenticated
                        else "User"
                    ),
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

            print("VERIFF RESPONSE:", response.text)

            response.raise_for_status()

            data = response.json()

            return Response({
                "session_url": data["verification"]["url"],
                "session_id": data["verification"]["id"]
            })

        except requests.exceptions.RequestException as e:

            print("VERIFF ERROR:", str(e))

            return Response(
                {"error": "Unable to create verification session"},
                status=status.HTTP_400_BAD_REQUEST
            )