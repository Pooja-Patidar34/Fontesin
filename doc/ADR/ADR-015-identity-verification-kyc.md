# ADR-015: Identity Verification (KYC)

## Status
Accepted (Internal)

## Context
The platform requires identity verification for certain user roles as part of regulatory compliance and trust-building.

Key requirements:
- Third-party KYC verification with document and facial recognition
- Secure session initiation from the backend (no client-side API key exposure)
- Webhook-based result delivery (asynchronous verification flow)
- HMAC signature verification on incoming webhooks to prevent spoofing
- Verification status persisted on the user model

## Decision
We integrate **Veriff** as the external KYC/identity verification provider.

### Flow
1. **Session Creation** — An authenticated user triggers a verification session via `CreateVeriffSessionAPIView`. The backend calls Veriff's API with the user's identity and receives a session URL.
2. **User Verification** — The user is redirected to Veriff's hosted verification UI, where they upload documents and complete facial recognition.
3. **Webhook Callback** — Veriff sends event and decision webhooks to `veriff_webhook`. The backend verifies the HMAC signature, processes the result, and updates the user's verification status.

### Components
- `accounts/view/veriff.py` — DRF API view for session creation
- `accounts/view/webhook.py` — Webhook endpoint with HMAC signature verification
- Configuration in `settings.py`:
  - `VERIFF_API_KEY` — API authentication
  - `VERIFF_MASTER_SECRET` — for session signing
  - `VERIFF_WEBHOOK_SECRET` — for webhook HMAC validation
  - `VERIFF_BASE_URL` — API base URL
  - `VERIFF_CALLBACK_URL` — post-verification redirect

### Security
- API keys are stored as environment variables, never in code
- Webhook payloads are validated using HMAC-SHA256 signatures
- Session creation requires authentication (`IsAuthenticated`)
- User ID is passed as `vendorData` to link verification results back to the correct user

## Rationale
- Veriff provides robust document + facial verification with global coverage
- Server-side session creation prevents API key exposure to clients
- HMAC webhook verification ensures only genuine Veriff payloads are processed
- Asynchronous webhook flow allows the user to complete verification at their own pace
- Status is stored on the user model for easy access in authorization decisions

## Consequences
- The verification flow depends on an external third-party service (Veriff availability)
- Webhook endpoint must be publicly accessible and exempt from CSRF protection
- `vendorData` linkage assumes user UUIDs are stable and unique
- Verification status updates are eventual (webhook delivery latency)
- Future work: retry logic for failed webhook deliveries, admin UI for manual verification override

## Alternatives Considered
- Onfido (evaluated — Veriff chosen for pricing and integration simplicity)
- Manual document upload + admin review (rejected — does not scale, no biometric verification)
- Client-side SDK integration (rejected — exposes API credentials)
