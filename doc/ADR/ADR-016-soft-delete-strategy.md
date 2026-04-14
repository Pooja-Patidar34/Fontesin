# ADR-016: Soft Delete Strategy

## Status
Accepted (Internal)

## Context
Certain entities in the system must not be permanently deleted from the database because:
- Audit trails and historical references require data to remain accessible
- Accidental deletions should be recoverable
- Foreign key relationships may reference soft-deleted records
- Compliance and data retention policies may require records to be kept

Key requirements:
- Mark records as deleted without removing them from the database
- Default queries should exclude soft-deleted records
- Explicit queries can still access soft-deleted records when needed
- Consistent implementation across all models that support soft delete

## Decision
We implement soft delete using an **`is_deleted` boolean field** combined with a custom **`ActiveManager`** that filters out deleted records by default.

### Components
- `accounts/common/active_manager.py` — custom Django manager that filters `is_deleted=False`
- Models that support soft delete include an `is_deleted = BooleanField(default=False)` field
- `ActiveManager` is assigned as the default manager (`objects`) on soft-deletable models
- Django's default manager is retained as `all_objects` for admin and audit access

### Soft-Deletable Models
- `Tenant` — tenants can be deactivated without losing historical data
- `Company` — companies may be archived but referenced by audit logs and invoices
- `User` — user accounts can be deactivated while preserving activity history

### Usage
```python
# Default queries exclude soft-deleted records
Tenant.objects.all()          # only active (is_deleted=False)

# Explicit access to all records including deleted
Tenant.all_objects.all()      # includes soft-deleted records

# Soft delete a record
tenant.is_deleted = True
tenant.save()
```

## Rationale
- Boolean flag is the simplest and most performant soft delete approach
- Custom manager ensures developers cannot accidentally query deleted records
- Retaining `all_objects` allows admin views and audit tools to access the full dataset
- No framework-level magic — the behavior is explicit and auditable
- Compatible with Django's ORM, migrations, and admin interface

## Consequences
- All queries via `objects` automatically exclude soft-deleted records
- Unique constraints must account for soft-deleted records (e.g., `unique_together` may need conditional indexes)
- Cascading deletes must be handled manually (soft-deleting a tenant should soft-delete related entities)
- Database storage grows over time; a periodic archival strategy may be needed
- Developers must use `all_objects` explicitly when they need to include deleted records

## Alternatives Considered
- Hard delete with audit log snapshots (rejected — loses relational integrity)
- Django third-party packages like `django-safedelete` (rejected — adds external dependency for a simple pattern)
- `deleted_at` timestamp field (evaluated — `is_deleted` boolean chosen for simplicity; timestamp can be added later if needed)
