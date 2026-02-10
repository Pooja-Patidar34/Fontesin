# Multi-Tenant Admin Panel
## Role-Based Access Control (RBAC) – Implementation Documentation

---

## 1. Project Overview

This project implements a custom multi-tenant admin panel using Django, designed to follow real-world backend engineering practices instead of relying on Django Admin or DRF.

The system demonstrates:

- Multi-tenant data isolation
- Multi-company user management
- Role-based access control (RBAC)
- Permission-driven authorization
- Immutable audit logging
- Centralized error handling (403 Forbidden)
- Template-based admin UI (AdminLTE)

The implementation is intentionally explicit and backend-focused to reflect production-grade architecture.

---

## 2. Architectural Principles

The system is built around the following core principles:

1. Tenant Isolation by Default  
   All business data is scoped to a tenant.

2. Multi-Company Support  
   Users may belong to multiple companies under the same tenant.

3. RBAC (Role-Based Access Control)  
   Permissions are assigned to roles, not directly to users.

4. Explicit Authorization  
   Every protected action checks permissions explicitly.

5. Fail-Secure Defaults  
   Access is denied unless explicitly allowed.

6. Immutability for Security Logs  
   Audit logs cannot be modified after creation.

7. Separation of Concerns  
   Models, permissions, views, error handling, and UI are clearly separated.

---

## 3. Model Architecture Overview

### Conceptual Relationship

Tenant
├── Companies
├── Users
│   ├── UserRoles ───────────> Roles ──> Permissions
│   └── UserCompanies
│       └── UserCompanyRoles ─> Roles ──> Permissions
└── AuditLogs

---

## 4. Model Design Explanation

### 4.1 Tenant

Purpose  
Represents an isolated organization or customer.

Key Design Decisions
- UUID primary key for security and scalability
- Slug for URL-safe identification
- is_active flag to disable tenants without deleting data

Why this is good practice
- Prevents cross-tenant data leakage
- Supports horizontal scaling
- Matches enterprise SaaS architecture

---

### 4.2 Company

Purpose  
Represents business entities under a tenant.

Key Design Decisions
- Strict tenant foreign key
- Unique constraint on (tenant, name)
- on_delete=PROTECT to prevent accidental data loss

---

### 4.3 Custom User Model

Purpose  
Custom authentication model using email instead of username.

Key Design Decisions
- Each user belongs to exactly one tenant
- Users may belong to multiple companies under the same tenant
- primary_company provides a default company context
- Email-based authentication
- is_staff may be used as a super-access shortcut
- PermissionsMixin retained for Django compatibility

---

### 4.4 UserCompany

Purpose  
Defines the association between users and companies.

Key Characteristics
- Many-to-many relationship between users and companies
- One company can be marked as primary per user
- Enforced uniqueness per (user, company)

Why this matters
- Enables multi-company access
- Supports company-scoped permissions
- Matches real-world enterprise access models

---

### 4.5 Permission

Purpose  
Atomic permission unit (e.g. user.view, company.manage).

Design Notes
- Permissions are global and reusable across tenants
- Assigned only through roles

---

### 4.6 Role

Purpose  
Logical grouping of permissions.

Design Notes
- Roles are tenant-scoped
- Reusable across companies
- Do not belong directly to companies

---

### 4.7 Role Assignment Strategy

The system supports role assignment at two levels:

Tenant-Level Roles (UserRole)
- Apply globally across the tenant
- Used for tenant admins, auditors, or operators

Company-Level Roles (UserCompanyRole)
- Apply only within a specific company
- Used for operational and business access control

This enables:
- Least-privilege enforcement
- Fine-grained authorization
- Clean separation of tenant vs company concerns

---

### 4.8 AuditLog (Security-Critical)

Purpose  
Tracks all sensitive or important actions.

Key Characteristics
- Tenant-scoped
- Actor-aware (nullable for system actions)
- Stores metadata and IP address

Critical Design Decision: Immutability

def save(self, *args, **kwargs):
    if not self._state.adding:
        raise RuntimeError("Audit logs are immutable")
    super().save(*args, **kwargs)

Why this matters
- Prevents tampering
- Supports compliance and forensic analysis
- Guarantees integrity of security logs

---

## 5. Permission Enforcement

- Permissions are checked explicitly in views
- Authorization is role-based, not user-based
- Permissions may be evaluated at tenant or company scope
- Staff users may be treated as super-access users if required
- Unauthorized access raises PermissionDenied

This ensures predictable and auditable access control.

---

## 6. Error Handling (403 Forbidden)

- Unauthorized access raises PermissionDenied
- Django renders a custom 403.html
- Centralized handling using handler403
- Clean UX without exposing internal details

This approach is preferred over returning HttpResponseForbidden().

---

## 7. Final Summary

This project demonstrates a production-ready Django backend architecture with:

- Strict tenant isolation
- Multi-company user associations
- Hierarchical RBAC (tenant + company level)
- Explicit permission enforcement
- Immutable audit logging
- Clean error handling

The design mirrors real-world enterprise SaaS authorization systems rather than simplified framework defaults.
