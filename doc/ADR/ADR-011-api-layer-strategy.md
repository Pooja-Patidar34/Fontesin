# ADR-011: API Layer Strategy

## Status
Accepted (Internal)

## Context
The system exposes both a server-rendered admin panel and a programmatic API consumed by external clients and frontend applications.

Key requirements:
- A consistent, well-documented HTTP API surface
- Schema-first or schema-derived API documentation
- Pluggable authentication (session for browser clients, JWT for API clients)
- Predictable serialization, validation, and error handling
- Clear separation between admin (template) views and API views

## Decision
We adopt **Django REST Framework (DRF)** as the sole API layer, combined with **drf-spectacular** for OpenAPI 3 schema generation.

### App Separation
- `accounts` — server-rendered admin panel views, forms, and templates
- `accounts_api` — DRF-based API views and serializers
- `billing` — domain-specific business logic, exposed as needed

This separation prevents accidental mixing of session-bound view logic with stateless API logic.

### Default Configuration
- `DEFAULT_AUTHENTICATION_CLASSES`:
  - `SessionAuthentication` (browser/admin clients)
  - `JWTAuthentication` (API clients)
- `DEFAULT_PERMISSION_CLASSES`: `IsAuthenticated`
- `DEFAULT_SCHEMA_CLASS`: `drf_spectacular.openapi.AutoSchema`

### API Documentation
- OpenAPI 3 schema is generated automatically by drf-spectacular
- The schema declares JWT bearer auth as the default security scheme
- Documentation reflects code, not the other way around

## Rationale
- DRF is the de-facto standard for building APIs in Django
- drf-spectacular generates accurate, code-derived schemas without duplication
- Authentication-by-default and permission-by-default reduce the risk of accidentally exposed endpoints
- Splitting `accounts` and `accounts_api` keeps view conventions, error handling, and response shapes coherent within each layer

## Consequences
- All API endpoints are authenticated unless explicitly opted out (via `AllowAny`)
- API and admin layers evolve independently and may need duplicate logic in some cases
- The OpenAPI schema is the single source of truth for API consumers
- Adding new authentication mechanisms requires updating DRF defaults in one place

## Alternatives Considered
- Plain Django views for the API (rejected — lacks serialization, content negotiation, and schema tooling)
- FastAPI as a sidecar service (rejected — operational overhead and duplication of identity logic)
- Manually maintained OpenAPI documents (rejected — drift risk between code and docs)
