# ADR-018: Configuration Management

## Status
Accepted (Internal)

## Context
The application requires different configuration values across environments (development, staging, production) including:
- Database credentials
- API keys for third-party services (Veriff, MailerSend)
- JWT signing keys
- Email provider settings
- Debug mode and allowed hosts
- Secret keys and webhook secrets

Key requirements:
- No secrets committed to version control
- Environment-specific configuration without code changes
- Simple local development setup
- Clear separation between code and configuration (12-factor app principles)

## Decision
We use **python-decouple** for all configuration management, loading values from environment variables with `.env` file fallback for local development.

### How It Works
- `from decouple import config` is used throughout `settings.py`
- Each setting is loaded via `config("KEY")` with optional `default` and `cast` parameters
- In development, values are read from a `.env` file in the project root
- In production, values are injected as real environment variables (via Docker, systemd, or hosting platform)
- `.env` is excluded from version control via `.gitignore`

### Configuration Categories
| Category | Examples |
|---|---|
| Core Django | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` |
| Database | `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` |
| JWT | Key files loaded from `keys/` directory |
| Email (SMTP) | `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` |
| Email (MailerSend) | `MAILERSEND_API_KEY`, `MAILERSEND_API_URL`, `MAILERSEND_FROM_EMAIL` |
| KYC (Veriff) | `VERIFF_API_KEY`, `VERIFF_MASTER_SECRET`, `VERIFF_WEBHOOK_SECRET` |

### Type Casting
- Boolean values: `config("DEBUG", default="True").lower() == "true"`
- Integer values: `config("EMAIL_PORT", default=587, cast=int)`
- List values: `config("ALLOWED_HOSTS", cast=lambda v: [...])`

## Rationale
- python-decouple is lightweight, has no dependencies, and follows 12-factor app conventions
- `.env` files provide a familiar developer experience without additional tooling
- Default values enable zero-configuration local development for non-sensitive settings
- Explicit `config()` calls make it clear which settings are externalized
- No configuration is hidden in framework-level magic or implicit environment detection

## Consequences
- Every deployment environment must provide the required environment variables
- Missing required variables (without defaults) cause immediate startup failure — this is intentional (fail-fast)
- `.env` files must never be committed; the repository should include a `.env.example` template
- JWT signing keys are loaded from files on disk (`keys/` directory), not from environment variables, due to their multi-line nature
- Adding a new external service requires adding its configuration keys to both the `.env.example` template and the settings module

## Alternatives Considered
- Django-environ (evaluated — similar functionality; python-decouple chosen for simpler API)
- Raw `os.environ` (rejected — no `.env` file support, no type casting, verbose)
- YAML/TOML config files (rejected — adds file format dependency, less standard for Django)
- Vault / AWS Secrets Manager (appropriate for production secret rotation but overkill for current scale; can be layered on later)
