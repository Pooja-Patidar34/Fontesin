# ADR-001: Authentication and Identity Strategy

## Status
Accepted (Internal)

## Context
The system requires secure authentication mechanisms suitable for an enterprise-grade, multi-tenant platform with both:

- A template-based admin panel
- API-based access for external or frontend consumers

Key requirements:
- Email/password authentication for admin users
- Token-based authentication for APIs
- Strong password hashing
- Clear separation between authentication (identity) and authorization (access control)
- Compatibility with Django’s authentication ecosystem
- Extensibility for future SSO or external identity providers

## Decision
We implement **two complementary authentication mechanisms**, depending on the access channel.

### 1. Admin Panel Authentication (Session-Based)
- Email and password–based login
- Uses a custom Django User model based on `AbstractBaseUser`
- Authentication handled via Django’s standard session framework

### 2. API Authentication (Token-Based)
- JWT-based authentication for APIs
- Asymmetric signing (public/private key pair)
- Tokens are issued after successful credential validation
- Token verification does not require database access

### Password Security
- Passwords are never stored in plain text
- Secure password hashing algorithms are used:
  - Argon2 (preferred)
  - bcrypt / PBKDF2 as fallback options
- Hashing is handled via Django’s password hasher framework

### Identity Model
- Email is used as the unique identifier (`USERNAME_FIELD = "email"`)
- `PermissionsMixin` is retained for Django compatibility only
- Custom `UserManager` enforces email normalization and creation rules

Authentication is strictly responsible for **identity verification**.  
Authorization decisions are handled separately via a custom RBAC system.

## Rationale
- Email/password authentication is well-suited for admin panel usage
- JWT with asymmetric signing is ideal for stateless API access
- Asymmetric JWT improves security and scalability
- Strong password hashing mitigates brute-force and credential theft risks
- Separating authentication from authorization reduces security coupling
- Retaining Django compatibility minimizes framework friction

## Consequences
- Two authentication flows must be maintained and tested
- Key management is required for JWT signing and rotation
- Admin panel access relies on session security
- API access remains stateless and scalable
- The system is prepared for future SSO or IdP integration
