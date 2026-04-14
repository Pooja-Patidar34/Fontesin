# ADR-014: Email Delivery Strategy

## Status
Accepted (Internal)

## Context
The system sends transactional emails for security-sensitive workflows including:
- Password reset OTPs
- Account verification (future)
- Notification emails (future)

Key requirements:
- Reliable delivery of security-critical emails
- Non-blocking email sending (must not slow down request response times)
- Configurable provider (development vs. production)
- Structured error logging on delivery failures
- No plain-text credentials in code

## Decision
We use **MailerSend** as the primary transactional email provider, called via its REST API. Email sending is executed in **background threads** to avoid blocking HTTP responses.

### Architecture
- `accounts/utils/mailer.py` contains all email delivery logic
- Public functions (e.g., `send_otp_email`) spawn a background `threading.Thread` that calls the MailerSend API
- The thread handles the HTTP request, error logging, and retry-free failure reporting
- Django's built-in `EMAIL_BACKEND` is retained as a fallback configuration for development (console backend)

### Configuration
All email settings are loaded from environment variables via `python-decouple`:
- `MAILERSEND_API_KEY` — API authentication
- `MAILERSEND_API_URL` — endpoint URL
- `MAILERSEND_FROM_EMAIL` / `MAILERSEND_FROM_NAME` — sender identity
- `EMAIL_BACKEND` — Django fallback (console in dev, SMTP if needed)

### Error Handling
- Connection errors, timeouts, and non-2xx responses are caught and logged to the `technical` logger
- No exceptions propagate to the calling view
- Failed sends return `False`; callers can decide whether to retry or alert

## Rationale
- MailerSend provides high deliverability and a simple REST API
- Background threads prevent email latency from affecting user experience
- Separating email logic into `utils/mailer.py` keeps views clean and testable
- Environment-based configuration supports seamless dev/staging/production switching
- Django's console backend enables local development without an email provider

## Consequences
- Background threads are fire-and-forget; delivery failures are logged but not retried automatically
- Thread-based async is suitable for low-volume transactional email; high-volume sending should use a task queue (Celery)
- Email templates are currently inline in Python code; future work may move them to HTML template files
- No delivery tracking or webhook integration for bounce/complaint handling yet

## Alternatives Considered
- Django `send_mail()` with SMTP (rejected — slower, less reliable for transactional email)
- Celery task queue (rejected for now — operational overhead not justified at current scale)
- SendGrid / AWS SES (evaluated — MailerSend chosen for pricing and simplicity)
