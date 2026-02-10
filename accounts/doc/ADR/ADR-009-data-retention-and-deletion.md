# ADR-009: Data Retention and Deletion Strategy

## Status
Accepted (Internal)

## Context
The system stores business, security, and operational data across multiple tenants.

Proper data retention and deletion are required to:
- Meet compliance and contractual obligations
- Minimize data exposure
- Support audits and forensic analysis
- Prevent accidental data loss

Different data categories require different retention behaviors.

## Decision
We implement a **category-based data retention strategy**, differentiating between:

- Core business data
- Security and audit data
- Operational and transient data

### Core Business Data
- Tenant, user, company, role, and permission data
- Managed using **soft-deletion** where applicable
- Deactivation (`is_active`) is preferred over hard deletion
- Hard deletion is restricted and controlled

### Security and Audit Data
- Audit logs are **append-only and immutable**
- Audit records are not modified or deleted under normal operation
- Retention duration is defined by compliance or contractual requirements
- Deletion, if required, is performed via controlled administrative procedures

### Operational and Transient Data
- Session data, caches, and temporary files
- Automatically expired or cleared
- Not considered part of long-term retention requirements

### Tenant Offboarding
- Tenant deactivation disables access immediately
- Data retention follows contractual or regulatory timelines
- Final deletion is performed only after explicit approval

## Rationale
- Differentiating data categories avoids one-size-fits-all retention
- Soft deletion reduces risk of accidental data loss
- Immutable audit data preserves forensic integrity
- Controlled deletion supports compliance and accountability

## Consequences
- Increased storage usage over time
- Additional operational processes for controlled deletion
- Clear and defensible data lifecycle management
- Improved compliance and audit readiness

## Alternatives Considered
- Immediate hard deletion of all data (rejected due to audit and recovery risks)
- Uniform retention for all data types (rejected due to compliance limitations)

## Notes
This strategy prioritizes **data safety, compliance, and accountability** over aggressive data cleanup.
