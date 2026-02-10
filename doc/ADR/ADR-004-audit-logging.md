# ADR-004: Audit Logging Strategy

## Status
Accepted (Internal)

## Context
The system must maintain a reliable, tamper-resistant audit trail for security-sensitive and business-critical actions.

Key requirements:
- Immutability of audit records
- Tenant-level isolation of audit data
- Clear actor attribution
- Support for structured metadata
- Audit and compliance readiness

Audit logs must be trustworthy and suitable for forensic analysis.

## Decision
We implement an **append-only AuditLog model** with the following characteristics:

- Each audit entry is explicitly associated with a tenant
- Actor attribution via an optional user reference
- Structured metadata stored as JSON
- IP address capture where available
- Model-level enforcement of immutability

Once created, audit records **cannot be updated or modified**.

### Immutability Enforcement
Immutability is enforced at the model layer by blocking updates to existing records.

## Rationale
- Prevents tampering with historical records
- Ensures integrity and trustworthiness of audit data
- Supports compliance and forensic investigation
- Aligns with enterprise security best practices
- Keeps security controls close to the data layer

## Consequences
- Audit records are append-only and permanent
- Corrections require compensating audit entries
- Storage usage increases over time
- Deletion of audit records is intentionally restricted

## Alternatives Considered
- Mutable audit logs (rejected due to tampering risk)
- Application-only logging without persistence (rejected due to lack of auditability)

## Notes
This strategy prioritizes **integrity and accountability** over convenience and storage efficiency.
