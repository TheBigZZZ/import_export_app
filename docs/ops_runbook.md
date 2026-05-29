# Ops Runbook (TradeDesk ERP)

This document lists production steps, secrets, and runbook tasks operators must perform.

## Required Environment Variables

- `TRADEDESK_ENVIRONMENT` set to `production`
- `TRADEDESK_JWT_SECRET_KEY` set to a cryptographically secure random secret
- `TRADEDESK_BCRYPT_ROUNDS` set to `12` or higher
- `TRADEDESK_DIAGNOSTICS_ADMIN_KEY` required if diagnostics are enabled in production
- `TRADEDESK_DIAGNOSTICS_NONCES_DIR` required path for nonce persistence when diagnostics are enabled in production
- Optional: `TRADEDESK_SENTRY_DSN` for Sentry error reporting
- Optional SMTP variables if diagnostics email notifications are enabled:
  - `TRADEDESK_DIAGNOSTICS_SMTP_HOST`
  - `TRADEDESK_DIAGNOSTICS_SMTP_USER`
  - `TRADEDESK_DIAGNOSTICS_SMTP_PASSWORD`

## Secrets and Monitoring

- Prefer environment variables for secrets.
- If the OS keyring is unavailable, the app falls back to an encrypted file store under `%USERPROFILE%/TradeDesk/data` and logs that fallback.
- Optional monitoring is available via `TRADEDESK_SENTRY_DSN` and the `/metrics` endpoint when `prometheus_client` is installed.

## One-Time Setup

1. Provision a server with Python 3.13 and the required OS packages.
2. Create an OS user for the app and a data directory such as `~/TradeDesk`.
3. Provide the environment variables via a systemd unit or container secret manager.
4. Apply database migrations before the first start:

```bash
python -m tradedesk.backend.cli --init-db
```

1. Optionally configure Sentry and monitoring.

## Backups

- Backups are stored in `${TRADEDESK_BACKUP_DIR}` with a default of `~/TradeDesk/backups`.
- You can create a manual backup:

```bash
python -m tradedesk.backend.cli --backup-db /var/backups/tradedesk
```

- To restore:

```bash
python -m tradedesk.backend.cli --restore-db /var/backups/tradedesk/tradedesk-db-20250101T120000Z.sqlite
```

## CI and Release Notes

- The CI workflow in `.github/workflows/ci.yml` runs tests, applies migrations in CI, generates an SBOM, and runs vulnerability checks.
- The scheduled daily backup workflow uploads backups as artifacts.

## Code Signing

- Code signing is not part of the current release scope.
- If signing is added later, keep it as a separate explicit release step so the smoke-tested unsigned build remains the default artifact.

## Monitoring

- The app supports optional Sentry integration via `TRADEDESK_SENTRY_DSN`.
- For metrics, install `prometheus_client` and enable a `/metrics` endpoint in the app.
- The backend writes a startup sentinel into the system temp folder and logs to the configured log directory so smoke and support tooling can confirm readiness.

## Troubleshooting

- If startup fails with `Startup safety check failed`, inspect environment variables and ensure migrations have been applied.
- If diagnostics uploads are rejected, ensure `TRADEDESK_DIAGNOSTICS_ADMIN_KEY` and the nonces directory are configured.
- If login or other API calls fail after a successful health check, inspect the backend log under the configured logs directory and the temp-folder startup sentinel.
