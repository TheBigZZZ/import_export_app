# Ops Runbook (TradeDesk ERP)

This document lists production steps, secrets, and runbook tasks operators must perform.

## Required environment variables (CI / server)
- `TRADEDESK_ENVIRONMENT` (set to `production`)
- `TRADEDESK_JWT_SECRET_KEY` — a cryptographically secure random secret.
- `TRADEDESK_BCRYPT_ROUNDS` — recommend `12` or higher.
- `TRADEDESK_DIAGNOSTICS_ADMIN_KEY` — required if diagnostics are enabled in production.
- `TRADEDESK_DIAGNOSTICS_NONCES_DIR` — required path for nonce persistence when diagnostics enabled in production.
- Optional: `TRADEDESK_SENTRY_DSN` for Sentry error reporting.
- Optional SMTP vars if diagnostics email notifications enabled:
  - `TRADEDESK_DIAGNOSTICS_SMTP_HOST`
  - `TRADEDESK_DIAGNOSTICS_SMTP_USER`
  - `TRADEDESK_DIAGNOSTICS_SMTP_PASSWORD`

## One-time setup
1. Provision a server with Python 3.13 and required OS packages.
2. Create an OS user for the app and a data directory (default `~/TradeDesk`).
3. Provide the environment variables via systemd unit or container secret manager.
4. Apply database migrations before first start:

```bash
python -m tradedesk.backend.cli --init-db
```

5. (Optional) Configure Sentry and monitoring.

## Backups
- Backups are stored in `${TRADEDESK_BACKUP_DIR}` (default `~/TradeDesk/backups`).
- You can create a manual backup:

```bash
python -m tradedesk.backend.cli --backup-db /var/backups/tradedesk
```

- To restore:

```bash
python -m tradedesk.backend.cli --restore-db /var/backups/tradedesk/tradedesk-db-20250101T120000Z.sqlite
```

## CI / Release notes
- The CI workflow (`.github/workflows/ci.yml`) runs tests, applies migrations in CI, generates SBOM and runs vulnerability checks.
- The scheduled daily backup workflow uploads backups as artifacts.

## Code signing
- For code signing, provide a Windows Authenticode certificate (`.pfx`) and set GitHub secrets:
  - `SIGNING_PFX` (base64-encoded .pfx)
  - `SIGNING_PASSWORD`
- CI can then run `signtool` on the built EXE in Windows runners; see packaging/README.md for more details.

## Monitoring
- The app supports optional Sentry integration via `TRADEDESK_SENTRY_DSN`.
- For metrics, install `prometheus_client` and enable `/metrics` endpoint in the app.

## Troubleshooting
- If startup fails with `Startup safety check failed`, inspect env vars and ensure migrations have been applied.
- If diagnostics uploads are rejected, ensure `TRADEDESK_DIAGNOSTICS_ADMIN_KEY` and nonces dir are configured.

*** End of runbook ***
