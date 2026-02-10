# ADR-003: Role-Based Access Control (RBAC) Strategy

## Status
Accepted (Internal)

## Context
The system requires fine-grained authorization suitable for an enterprise-grade, multi-tenant platform.

Key requirements:
- Enforcement of least-privilege access
- Clear separation between identity and authorization
- Support for tenant-wide and company-scoped permissions
- Avoidance of Django’s default Group-based authorization
- Explicit and auditable permission checks

The authorization model must scale with organizational complexity while remaining predictable and secure.

## Decision
We implement a **custom Role-Based Access Control (RBAC) model** with explicit separation of concerns.

The RBAC system consists of:
- **Permission**: Atomic, reusable authorization units
- **Role**: A logical grouping of permissions
- **UserRole**: Assigns roles to users at the tenant level
- **UserCompanyRole**: Assigns roles to users within a specific company

Permissions are **never assigned directly to users**.

### Scope of Roles
- **Tenant-level roles** apply across the entire tenant and are used for administrative or cross-company access.
- **Company-level roles** apply only within the context of a specific company.

## Rationale
- Mirrors real-world IAM and enterprise RBAC systems
- Prevents permission sprawl and ad-hoc access grants
- Enables reusable, centrally managed authorization policies
- Supports multi-company access patterns under a single tenant
- Keeps authorization logic explicit and auditable

## Consequences
- Authorization checks must be explicitly implemented in views or service layers
- Slightly higher modeling and implementation complexity
- Significantly improved security posture and maintainability
- Clear separation of tenant-wide vs company-scoped access

## Alternatives Considered
- Django Groups and permissions (rejected due to limited flexibility and implicit behavior)
- Direct permission assignment to users (rejected due to poor auditability and risk of privilege sprawl)

## Notes
This RBAC strategy prioritizes **clarity, least privilege, and auditability** over convenience and implicit framework behavior.
