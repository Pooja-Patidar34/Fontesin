import logging
import traceback
from FontEsin.middleware.correlation_id import get_correlation_id

technical_logger = logging.getLogger("technical")


class ErrorLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        try:
            response = self.get_response(request)
            return response

        except Exception as e:

            # Default status
            status_code = 500

            # If exception provides HTTP status code
            if hasattr(e, "status_code"):
                status_code = e.status_code

            user_id = None
            tenant_id = None

            if hasattr(request, "user") and request.user.is_authenticated:
                user_id = request.user.id
                tenant_id = getattr(request.user, "tenant_id", None)

            technical_logger.error(
                "unhandled_exception",
                extra={
                    "correlation_id": get_correlation_id(),
                    "actor": user_id,
                    "tenant": tenant_id,
                    "endpoint": request.path,
                    "status": status_code,
                    "metadata": {
                        "method": request.method,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                },
            )

            raise