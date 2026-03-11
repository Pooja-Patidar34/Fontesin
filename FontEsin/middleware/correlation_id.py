import uuid
import threading

_local = threading.local()

def get_correlation_id():
    return getattr(_local, "correlation_id", None)


class CorrelationIDMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        correlation_id = request.headers.get("X-Correlation-ID")

        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        _local.correlation_id = correlation_id
        request.correlation_id = correlation_id

        response = self.get_response(request)

        response["X-Correlation-ID"] = correlation_id

        return response