# Production Readiness Checklist and Steps

This document lists the minimum steps to prepare TradeDesk for production, how to manage secrets, migrations, monitoring, packaging, and signing.

## Environment Variables

Set these minimum values for production:

- `TRADEDESK_ENVIRONMENT=production`
- `TRADEDESK_JWT_SECRET_KEY` set to a strong random secret
- `TRADEDESK_ASYNC_DATABASE_URL` optional, defaults to the SQLite file in the data directory; for production consider Postgres
- `TRADEDESK_SENTRY_DSN` optional, only if you are using Sentry

## Migration and Database Initialization

Do not rely on `Base.metadata.create_all` in production. Run migrations explicitly:

```bash
python -m tradedesk.backend.cli --init-db
```

Or use Alembic directly:

```bash
alembic -c tradedesk/backend/alembic.ini upgrade head
```

Recommended backup and retention settings:

- `DIAGNOSTICS_UPLOAD_MAX_BYTES=5242880` for the 5 MB default
- `DIAGNOSTICS_RETENTION_DAYS=30`
- `DIAGNOSTICS_ALLOW_SELF_REGISTER=false`
- `DIAGNOSTICS_ADMIN_KEY` set if you need install registration

## Secrets Management

- Store `TRADEDESK_JWT_SECRET_KEY` and database passwords in your OS secret store or in CI/CD secrets.
- Do not check secrets into source control or `.env` files.
- Consider a secrets manager such as Azure Key Vault, AWS Secrets Manager, or HashiCorp Vault.
- In CI, add repository secrets only for the values you actually need.

## Monitoring and Error Reporting

- Enable Sentry by setting `TRADEDESK_SENTRY_DSN` in the production environment or CI secrets if you want Sentry.
- Sentry provides grouped stack traces, release tracking, and alerting.
- Alternatively, send structured JSON logs to a log collector such as Loki, ELK, or Cloud Logging.

## Logging

- The backend emits structured JSON logs when no external logging config is present.
- Ensure your log collection captures STDOUT and STDERR.

## Packaging and Signing

- The repository contains an Inno Setup script and a PyInstaller spec.
- To avoid SmartScreen warnings, obtain a code-signing certificate and sign the EXE and installer with `signtool`.
- GitHub Actions can build the Windows EXE and upload the dist artifact.

## CI and Automated Releases

Add repository secrets only if your CI workflow needs them:

- `TRADEDESK_JWT_SECRET_KEY`
- `SENTRY_DSN` if you use Sentry
- `CODESIGN_CERT` if you sign in CI
- `CODESIGN_CERT_PASS` if your certificate requires a password

## Operational Runbook

- Back up the database file regularly, ideally daily, into `TRADEDESK_BACKUP_DIR`.
- Create monitoring alerts for error spikes and availability checks on `/health`.

## Quick Safety Checklist Before First Production Deploy

- Set environment to production and ensure `TRADEDESK_DEBUG=false`.
- Run migrations with `python -m tradedesk.backend.cli --init-db`.
- Verify `/health` returns `{"status":"ok"}`.
- Start the packaged installer and verify the app launches and the backend is reachable.

If you'd like, I can also add a CI secret setup snippet and example code-signing commands.
