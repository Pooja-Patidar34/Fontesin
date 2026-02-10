# ADR-006: JWT Key Management Strategy

## Status
Accepted (Internal)

## Context
The system uses JWT-based authentication with asymmetric signing for API access.

Secure key management is required to ensure:
- Token integrity and authenticity
- Protection of private signing keys
- Safe and efficient token verification
- Compliance and audit readiness

## Decision
We adopt an **asymmetric JWT key management strategy** using a public/private key pair.

### Key Usage
- Private key is used exclusively for signing JWTs
- Public key is used for verifying JWT signatures
- Private keys are never exposed to clients or committed to source control

### Key Storage
- Private keys are stored securely using:
  - Environment variables (baseline)
  - External secrets manager in production environments
- Public keys may be distributed for verification purposes
- All cryptographic material is excluded from version control

### Key Rotation
- JWTs include a key identifier (`kid`) header
- Multiple public keys may be valid simultaneously
- Old keys are retired only after issued tokens expire
- Rotation is performed without service downtime

### Access Control
- Only the authentication component has access to private keys
- Verification components require public keys only
- No database access is required for token verification

## Rationale
- Asymmetric signing enables stateless and scalable authentication
- Private key isolation limits blast radius in case of compromise
- Public key verification simplifies distributed validation
- Key rotation support aligns with security best practices
- Avoids shared-secret risks associated with symmetric JWTs

## Consequences
- Additional operational responsibility for key management
- Slightly increased configuration complexity
- Improved security posture and scalability
- Clear audit trail for cryptographic controls

## Notes
This strategy prioritizes **security, scalability, and auditability** for API authentication.
