import json
import re

from django.http import JsonResponse

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "\U0000FE00-\U0000FE0F"
    "\U0001F000-\U0001F02F"
    "\U0001F0A0-\U0001F0FF"
    "\U0001F100-\U0001F1FF"
    "\U0001F200-\U0001F2FF"
    "]+",
    flags=re.UNICODE,
)


def _contains_emoji(value):
    if isinstance(value, str):
        return bool(EMOJI_PATTERN.search(value))
    if isinstance(value, dict):
        return any(_contains_emoji(v) or _contains_emoji(k) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_emoji(item) for item in value)
    return False


class NoEmojiMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            for key, value in request.POST.items():
                if _contains_emoji(key) or _contains_emoji(value):
                    return self._reject(key)

            content_type = request.content_type or ""
            if "application/json" in content_type and request.body:
                try:
                    payload = json.loads(request.body.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    payload = None
                if payload is not None and _contains_emoji(payload):
                    return self._reject()

        for key, value in request.GET.items():
            if _contains_emoji(key) or _contains_emoji(value):
                return self._reject(key)

        return self.get_response(request)

    @staticmethod
    def _reject(field=None):
        message = "Emojis are not allowed in input."
        if field:
            message = f"Emojis are not allowed in input '{field}'."
        return JsonResponse({"error": message}, status=400)
