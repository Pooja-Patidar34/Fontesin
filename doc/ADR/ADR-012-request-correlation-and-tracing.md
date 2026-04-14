# ADR-012: Request Correlation and Tracing

## Status
Accepted (Internal)

## Context
In a multi-tenant platform handling concurrent requests, diagnosing issues across middleware, views, and external services requires a reliable way to link all log entries generated during a single request.

Key requirements:
- Trace a request end-to-end from ingress to response
- Correlate logs across middleware, views, and background tasks
- Support external correlation IDs forwarded by upstream proxies or gateways
- Minimal performance overhead

## Decision
We implement a **middleware-based correlation ID** strategy using a custom `CorrelationIDMiddleware`.

### How It Works
1. On each incoming request, the middleware checks for an `X-Correlation-ID` header.
2. If present, the header value is reused; otherwise, a new UUID v4 is generated.
3. The correlation ID is stored in `threading.local()` and attached to `request.correlation_id`.
4. The response includes the same `X-Correlation-ID` header for client-side tracing.
5. A custom logging filter (`CorrelationIdFilter`) injects the correlation ID into every log record.
6. A custom JSON formatter (`JSONFormatter`) serializes the correlation ID into structured log output.

### Components
- `FontEsin/middleware/correlation_id.py` — middleware + thread-local accessor
- `FontEsin/logging/correlation_filter.py` — logging filter
- `FontEsin/logging/json_formatter.py` — structured JSON log formatter
- `FontEsin/middleware/request_logging.py` — request lifecycle logging (uses correlation ID)
- `FontEsin/middleware/error_logging.py` — unhandled exception logging (uses correlation ID)

## Rationale
- UUID-based correlation IDs are simple, unique, and framework-agnostic
- Thread-local storage is safe in Django's synchronous request model
- Reusing upstream `X-Correlation-ID` allows end-to-end tracing through load balancers and API gateways
- Injecting the ID at the logging filter level ensures every log statement includes it automatically
- JSON-formatted logs are easily indexed by log aggregation tools (ELK, Datadog, CloudWatch)

## Consequences
- All log entries include a `correlation_id` field by default
- Tracing works out of the box for synchronous requests; async or Celery tasks require explicit propagation
- Slight overhead per request (UUID generation + thread-local write) — negligible
- Requires structured log parsing in production monitoring stack

## Notes
If the project adopts async views or background task queues, the correlation ID propagation must be extended to those execution contexts (e.g., passing the ID via task headers in Celery).
