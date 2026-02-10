# ADR-002: Multi-Tenancy Strategy

## Status
Accepted (Internal)

## Context
The application is designed as a multi-tenant system where multiple organizations share the same infrastructure while remaining logically and securely isolated.

Key requirements:
- Strong tenant isolation
- Prevention of cross-tenant data access
- Predictable and auditable data boundaries
- Compatibility with enterprise SaaS patterns
- Scalability without architectural rework

The system must support multiple tenants without relying on implicit context or framework-level magic.

## Decision
We implement a **single-database, row-level multi-tenancy strategy** using an explicit `Tenant` model.

All core domain entities are **explicitly scoped to a tenant** using foreign key relationships.

Tenant scoping is enforced at the application and data-model level rather than through implicit middleware injection.

### Tenant-Scoped Models
The following models include a mandatory foreign key to `Tenant`:
- User
- Company
- Role
- AuditLog

No shared mutable business data exists without tenant association.

## Rationale
- Explicit tenant foreign keys make data boundaries visible and enforceable
- Prevents accidental cross-tenant queries and joins
- Simplifies auditing and security reviews
- Avoids hidden coupling caused by request-scoped globals
- Aligns with common enterprise SaaS and IAM architectures
- Compatible with future database sharding or tenant-based partitioning

## Consequences
- All queries must explicitly include tenant filtering
- Developers must remain tenant-aware when writing data access logic
- Cross-tenant joins are structurally impossible
- Slightly more verbose code in exchange for strong isolation guarantees

## Alternatives Considered
- Separate database per tenant (rejected due to operational complexity)
- Schema-based tenancy (rejected due to migration and tooling overhead)
- Middleware-injected tenant context (rejected due to hidden coupling and audit complexity)

## Notes
This strategy prioritizes **clarity, security, and auditability** over convenience and implicit behavior.
