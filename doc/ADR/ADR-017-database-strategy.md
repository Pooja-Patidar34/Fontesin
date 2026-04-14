# ADR-017: Database Strategy

## Status
Accepted (Internal)

## Context
The platform requires a robust, production-grade relational database that supports:
- Complex multi-tenant queries with strong data isolation
- UUID primary keys across all models
- JSON fields for flexible metadata storage
- Full ACID compliance for financial and audit data
- Indexing strategies for tenant-scoped lookups
- Compatibility with Django's ORM and migration framework

## Decision
We use **PostgreSQL** as the sole relational database for all environments (development, staging, production).

### Configuration
- Database connection is configured via environment variables (`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`)
- Connection timeout is set to 5 seconds to fail fast on connectivity issues
- Django's `django.db.backends.postgresql` engine is used

### Schema Design Principles
- **UUID primary keys** on all models (`models.UUIDField(primary_key=True, default=uuid.uuid4)`)
- **Composite indexes** for tenant-scoped lookups (e.g., `tenant + email`, `tenant + name`)
- **`unique_together` constraints** for cross-tenant uniqueness
- **`JSONField`** for flexible metadata (audit log metadata, plan features, plan comparison data)
- **Foreign key constraints** with appropriate `on_delete` policies (`PROTECT`, `CASCADE`, `SET_NULL`)
- **Conditional unique constraints** for business rules (e.g., one active subscription per user)

### Data Integrity
- `PROTECT` on critical relationships (Tenant, Role) to prevent accidental cascade deletions
- `CASCADE` on owned relationships (enrichment data, junction tables)
- `SET_NULL` on optional relationships (owner, consultant)
- Database-level constraints enforce business rules that cannot be bypassed at the application level

## Rationale
- PostgreSQL is the most capable open-source relational database for Django
- Native UUID support avoids the overhead of string-based UUIDs
- Native JSONField eliminates the need for a separate NoSQL store for metadata
- Conditional unique constraints (`UniqueConstraint` with `condition`) enable complex business rules at the database level
- Strong ecosystem: pg_dump for backups, pgBouncer for connection pooling, PostGIS for future geospatial needs
- Django's PostgreSQL backend is the most well-tested and feature-complete

## Consequences
- All environments must run PostgreSQL (no SQLite for development)
- UUIDs are non-sequential, which affects index locality — mitigated by composite indexes
- JSON fields should be used for metadata only, not for structured data that needs relational integrity
- Connection pooling (pgBouncer) is recommended for production deployments
- Database backups and point-in-time recovery must be configured at the infrastructure level

## Alternatives Considered
- SQLite for development (rejected — behavior differences between SQLite and PostgreSQL cause subtle bugs)
- MySQL / MariaDB (rejected — weaker JSON support, no conditional unique constraints)
- MongoDB for metadata (rejected — adds operational complexity; PostgreSQL's JSONField is sufficient)
