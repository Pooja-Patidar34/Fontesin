# ADR-007: Secrets Management Strategy

## Status
Accepted (Internal)

## Context
The system handles multiple sensitive secrets that are critical to its security and correct operation, including:

- JWT private keys used for asymmetric signing
- Django `SECRET_KEY`
- Database credentials
- Third-party service credentials (if applicable)

Improper handling of secrets can result in credential leakage, unauthorized access, or full system compromise.

Key requirements:
- Secrets must never be committed to source control
- Secrets must be environment-specific
- Access to secrets must be strictly limited
- The strategy must support audits and future scaling

## Decision
We adopt an **environment-based secrets management strategy**, fully separating secrets from application code.

### Storage Strategy
- Secrets are stored outside the codebase using:
  - Environment variables (baseline approach)
  - A managed secrets service in production environments where available
- Secrets are explicitly excluded from version control using `.gitignore`
- No secrets are hardcoded in source files or configuration files committed to the repository

### Managed Secrets
The following are treated as sensitive secrets:
- `DJANGO_SECRET_KEY`
- JWT private keys
- Database usernames and passwords
- External API keys or credentials
- Any cryptographic material

### Environment Separation
- Each environment (development, staging, production) uses separate secrets
- Production secrets are never shared with development or staging
- Development secrets are considered disposable

### Access Control
- Only the application runtime has access to required secrets
- Developers do not require access to production secrets
- Access is limited to the minimum scope required for operation

## Rationale
- Separating secrets from code reduces the risk of accidental exposure
- Environment-based configuration follows Twelve-Factor App principles
- Limits the blast radius in case of credential compromise
- Simplifies rotation and revocation of secrets
- Aligns with common security and compliance expectations

## Consequences
- Operational responsibility for provisioning and rotating secrets
- Additional environment configuration overhead
- Improved overall security posture
- Clear audit trail for how sensitive values are managed

## Notes
This strategy prioritizes **confidentiality, operational safety, and auditability** over developer convenience.
