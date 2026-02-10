# ADR-005: Authorization Enforcement Strategy

## Status
Accepted (Internal)

## Context
The system requires consistent, predictable, and auditable authorization enforcement across all access paths, including:

- Admin panel views
- API endpoints
- Tenant-scoped and company-scoped operations

Authorization must prevent unauthorized access, avoid implicit privilege escalation, and remain easy to review and audit.

## Decision
Authorization is enforced **explicitly at the application layer**.

The enforcement strategy includes:
- Permission checks performed in views or service-layer functions
- Authorization decisions based on RBAC (roles and permissions)
- Explicit tenant and company context evaluation where applicable
- Unauthorized access raising `PermissionDenied`
- Centralized handling of authorization failures using a custom 403 error page

No authorization is performed implicitly by framework defaults.

## Rationale
- Explicit authorization logic is easier to reason about and review
- Prevents accidental permission bypass through framework shortcuts
- Makes security boundaries visible and testable
- Improves auditability and compliance readiness
- Aligns with least-privilege access principles

## Consequences
- Authorization checks must be written and maintained explicitly
- Slightly increased boilerplate in views or services
- Clear and enforceable security boundaries
- Reduced risk of privilege escalation or access leaks

## Alternatives Considered
- Relying on Django Admin or implicit permission checks (rejected due to lack of control and auditability)
- Silent authorization failures (rejected due to poor security posture and UX)

## Notes
This strategy prioritizes **security, clarity, and auditability** over convenience and implicit framework behavior.
