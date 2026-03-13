import time
import logging

from FontEsin.middleware.correlation_id import get_correlation_id

technical_logger = logging.getLogger("technical")


class RequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Skip static files
        if request.path.startswith("/static") or request.path == "/favicon.ico":
            return self.get_response(request)

        start_time = time.time()

        user_id = None
        tenant_id = None
        status_code = 500

        try:
            response = self.get_response(request)
            status_code = response.status_code
            return response

        finally:
            duration = round((time.time() - start_time) * 1000, 2)

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
                    "status": status_code,
                    "metadata": {
                        "method": request.method,
                        "duration_ms": duration,
                    },
                },
            )