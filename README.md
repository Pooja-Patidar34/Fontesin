# 🏗️ Multi-Tenant Admin Panel  
## Role-Based Access Control (RBAC) – Implementation Documentation

---

## 1. Project Overview

This project implements a **custom multi-tenant admin panel** using Django, designed to follow **real-world backend engineering practices** instead of relying on Django Admin or DRF.

The system demonstrates:

- Multi-tenant data isolation  
- Role-based access control (RBAC)  
- Permission-driven authorization  
- Immutable audit logging  
- Centralized error handling (403 Forbidden)  
- Template-based admin UI (AdminLTE)  

The implementation is intentionally explicit and backend-focused to reflect **production-grade architecture**.

---

## 2. Architectural Principles

The system is built around the following core principles:

1. **Tenant Isolation by Default**  
   All business data is scoped to a tenant.

2. **RBAC (Role-Based Access Control)**  
   Permissions are assigned to roles, not directly to users.

3. **Explicit Authorization**  
   Every protected action checks permissions explicitly.

4. **Fail-Secure Defaults**  
   Access is denied unless explicitly allowed.

5. **Immutability for Security Logs**  
   Audit logs cannot be modified after creation.

6. **Separation of Concerns**  
   Models, permissions, views, error handling, and UI are clearly separated.

---

## 3. Model Architecture Overview

### Conceptual Relationship

```
Tenant
├── Companies
├── Users
│   └── UserRoles ──> Roles ──> Permissions
├── Classifications
└── AuditLogs
```

---

## 4. Model Design Explanation

### 4.1 Tenant

**Purpose**  
Represents an isolated organization or customer.

**Key Design Decisions**
- UUID primary key for security and scalability  
- `slug` for URL-safe identification  
- `is_active` flag to disable tenants without deleting data  

**Why this is good practice**
- Prevents cross-tenant data leakage  
- Supports horizontal scaling  
- Matches enterprise SaaS architecture  

---

### 4.2 Company

**Purpose**  
Represents business entities under a tenant.

**Key Design Decisions**
- Strict tenant foreign key  
- `unique_together (tenant, name)` to avoid duplicates  
- `on_delete=PROTECT` to prevent accidental data loss  

---

### 4.3 Custom User Model

**Purpose**  
Custom authentication model using email instead of username.

**Key Design Decisions**
- One user belongs to exactly one tenant  
- Email-based login  
- `is_staff` used as a super-permission shortcut  
- `PermissionsMixin` retained for Django compatibility  

---

### 4.4 Classification

**Purpose**  
Tenant-specific lookup/configuration values (e.g. statuses, labels).

---

### 4.5 Permission

**Purpose**  
Atomic permission unit (e.g. `user.view`, `company.manage`).

---

### 4.6 Role

**Purpose**  
Logical grouping of permissions.

---

### 4.7 UserRole

**Purpose**  
Assigns roles to users.

---

### 4.8 AuditLog (Security-Critical)

**Purpose**  
Tracks all sensitive or important actions.

**Critical Design Decision: Immutability**

```python
def save(self, *args, **kwargs):
    if self.pk:
        raise RuntimeError("Audit logs are immutable")
```

**Why this matters**
- Prevents tampering  
- Supports compliance and forensic analysis  
- Guarantees integrity of security logs  

---

## 5. Permission Enforcement

- Permissions are checked explicitly in views
- Authorization is role-based, not user-based
- Staff users can be treated as super-access users if required
- Unauthorized access raises `PermissionDenied`

This ensures predictable and auditable access control.

---

## 6. Error Handling (403 Forbidden)

- Unauthorized access raises `PermissionDenied`
- Django renders a custom `403.html`
- Centralized handling using `handler403`
- Clean UX without exposing internal details

This approach is preferred over returning `HttpResponseForbidden()`.

---

## 7. Final Summary

This project demonstrates a **production-ready Django backend architecture** with:

- Strong security guarantees  
- Explicit authorization  
- Scalable RBAC design  
- Tenant-isolated data model  
- Immutable audit logging  
- Clean error handling  

The implementation reflects **real-world enterprise backend practices.
