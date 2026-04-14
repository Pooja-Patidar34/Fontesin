# ADR-013: Rate Limiting and Throttling

## Status
Accepted (Internal)

## Context
Public-facing and authenticated API endpoints are vulnerable to abuse, brute-force attacks, and accidental overuse. Rate limiting is necessary to:
- Protect authentication endpoints from credential-stuffing attacks
- Prevent resource exhaustion from misbehaving clients
- Ensure fair usage across tenants and users
- Provide a baseline defense before infrastructure-level WAF rules

## Decision
We use **DRF's built-in throttling framework** with two default throttle classes applied globally.

### Configuration
```python
DEFAULT_THROTTLE_CLASSES = (
    "rest_framework.throttling.AnonRateThrottle",
    "rest_framework.throttling.UserRateThrottle",
)

DEFAULT_THROTTLE_RATES = {
    "anon": "100/min",
    "user": "200/min",
}
```

### How It Works
- **AnonRateThrottle** — limits unauthenticated requests to 100 per minute, keyed by IP address.
- **UserRateThrottle** — limits authenticated requests to 200 per minute, keyed by user ID.
- Throttling is enforced at the DRF layer before views execute.
- Individual views can override throttle classes or rates as needed.

## Rationale
- DRF's throttling is simple, well-tested, and requires no external dependencies
- IP-based anonymous throttling protects login and registration endpoints
- User-based throttling prevents authenticated abuse without penalizing shared IPs
- Global defaults ensure every endpoint is protected by default
- Per-view overrides allow sensitive endpoints (e.g., password reset) to be more restrictive

## Consequences
- All API endpoints are rate-limited by default
- Shared-IP environments (corporate NATs) may experience false positives on anonymous throttling
- Throttle state is stored in Django's default cache (in-memory by default); production deployments should use Redis or Memcached for distributed rate limiting
- More granular rate policies (per-tenant, per-endpoint) can be added as custom throttle classes

## Notes
- Consider migrating to Redis-backed cache for throttle state in production to ensure consistency across multiple application servers.
- Sensitive endpoints (login, forgot-password, OTP verification) should be reviewed for stricter per-endpoint rate limits.
