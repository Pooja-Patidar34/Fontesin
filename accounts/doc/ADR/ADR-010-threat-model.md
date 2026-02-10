# ADR-010: Threat Model (STRIDE-lite)

## Status
Accepted (Internal)

## Context
The system is a multi-tenant, role-based admin platform with both session-based and JWT-based authentication.

A lightweight threat model is required to:
- Identify common security threats
- Document mitigations already in place
- Support security reviews, audits, and future hardening
- Avoid excessive complexity or speculative threats

This model follows a simplified STRIDE approach.

---

## Threat Categories and Mitigations

### 1. Spoofing Identity
**Threat**
- Attackers impersonating legitimate users
- Token theft or credential reuse

**Mitigations**
- Email/password authentication with strong hashing (Argon2/bcrypt)
- JWT-based API authentication using asymmetric signing
- Secure session management for admin panel
- Authentication and authorization separation
- No plain-text credentials stored

---

### 2. Tampering with Data
**Threat**
- Unauthorized modification of business or audit data
- Manipulation of audit records

**Mitigations**
- Explicit authorization enforcement via RBAC
- Tenant-scoped data access
- Immutable, append-only audit logs
- Database-level constraints and foreign keys
- No shared mutable cross-tenant data

---

### 3. Repudiation
**Threat**
- Users denying having performed sensitive actions

**Mitigations**
- Persistent audit logging of security-sensitive actions
- Actor attribution where applicable
- Timestamped and tenant-scoped audit records
- Compensating audit entries instead of mutation

---

### 4. Information Disclosure
**Threat**
- Exposure of sensitive or cross-tenant data
- Leakage of secrets or tokens via logs

**Mitigations**
- Explicit tenant scoping in all queries
- Secrets management via environment variables or secret stores
- No logging of credentials, tokens, or secrets
- Restricted access to logs and audit data
- Use of UUIDs to reduce enumeration risk

---

### 5. Denial of Service
**Threat**
- Resource exhaustion or abuse of authentication endpoints

**Mitigations**
- Stateless JWT verification (no database dependency)
- Separation of admin and API access paths
- Infrastructure-level monitoring and alerting
- Controlled authentication flows

---

### 6. Elevation of Privilege
**Threat**
- Users gaining higher permissions than intended
- Misuse of staff or administrative flags

**Mitigations**
- Role-based access control (RBAC)
- Explicit permission checks in application logic
- No implicit privilege escalation
- Clear separation between identity and authorization
- Avoidance of framework-default permission shortcuts

---

## Out of Scope
The following are intentionally excluded from this threat model:
- Network-level attacks (handled by infrastructure)
- Client-side vulnerabilities
- Advanced persistent threats (APT)
- Zero-day framework vulnerabilities

---

## Rationale
A STRIDE-lite model provides sufficient security visibility without overengineering.

This approach:
- Documents realistic threats
- Demonstrates existing mitigations
- Supports audits and reviews
- Leaves room for future deep-dive security analysis

---

## Consequences
- Some threats are mitigated operationally rather than in code
- Deeper threat modeling may be required for high-risk deployments
- Provides a clear baseline for future security enhancements

---

## Notes
This threat model is intended as a **living document** and should be revisited when major architectural changes occur.
