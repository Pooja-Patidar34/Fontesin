import time
import logging

from FontEsin.middleware.correlation_id import get_correlation_id


technical_logger = logging.getLogger("technical")


class RequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        start_time = time.time()

        response = self.get_response(request)

        duration = round((time.time() - start_time) * 1000, 2)

        user_id = None
        tenant_id = None

        if request.user.is_authenticated:
            user_id = request.user.id
            tenant_id = getattr(request.user, "tenant_id", None)

        technical_logger.info(
            "api_request",
            extra={
                "correlation_id": get_correlation_id(),
                "actor": user_id,
                "tenant": tenant_id,
                "endpoint": request.path,
                "method": request.method,
                "status": response.status_code,
                "metadata": {
                    "duration_ms": duration
                }
            }
        )

        return response