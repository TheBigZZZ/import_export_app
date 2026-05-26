Production Readiness Checklist and Steps

This document lists the minimum steps to prepare TradeDesk for production, how to manage secrets, migrations, monitoring, packaging, and signing.

1) Environment variables (minimum)
  - TRADEDESK_ENVIRONMENT=production
  - TRADEDESK_JWT_SECRET_KEY="<strong-random-secret>"
  - TRADEDESK_ASYNC_DATABASE_URL optional (defaults to sqlite file in data dir). For production consider Postgres.
  - TRADEDESK_SENTRY_DSN optional (if using Sentry)

2) Migration / DB initialization
  2) Migration / DB initialization
    - DIAGNOSTICS_UPLOAD_MAX_BYTES=5242880  (5MB default)
    - DIAGNOSTICS_RETENTION_DAYS=30
  - Do NOT rely on `Base.metadata.create_all` in production. Run migrations explicitly:

    Python (programmatic):
    ```bash
    python -m tradedesk.backend.cli --init-db
    ```

    Or using Alembic directly:
    ```bash
    alembic -c tradedesk/backend/alembic.ini upgrade head
    ```
    - DIAGNOSTICS_ALLOW_SELF_REGISTER=false
    - DIAGNOSTICS_ADMIN_KEY=  # optional admin key to register installs

3) Secrets management
  - Store `TRADEDESK_JWT_SECRET_KEY` and any DB passwords in your OS secret store or in your CI/CD secrets (do NOT check into source or `.env`).
  - Recommended: use a secrets manager (Azure KeyVault, AWS Secrets Manager, HashiCorp Vault). In CI add repository secrets `TRADEDESK_JWT_SECRET_KEY`, `SENTRY_DSN`, `CODESIGN_CERT` etc.

4) Monitoring & error reporting (minimal recommended setup)
  - Enable Sentry by setting `TRADEDESK_SENTRY_DSN` in production environment or CI secrets. The backend will initialize Sentry automatically when the DSN is present.
  - Sentry gives grouped stacktraces, release tracking and alerting with minimal setup.
  - Alternatively: send structured JSON logs to a log collector (Loki/ELK/Cloud Logging).

5) Logging
  - The backend config now emits structured JSON logs when no external config is present. Ensure your log collection captures STDOUT/STDERR.

6) Packaging & signing
  - The repository contains an Inno Setup script and a PyInstaller spec. To avoid SmartScreen warnings, obtain a code-signing cert and sign the EXE and installer with `signtool`.
  - CI: Add a `build-windows-exe` job and store code-sign artifacts as secrets. The current GitHub Actions workflow uploads the dist artifact.

7) CI and automated releases
  - Add the following repository secrets for CI: `TRADEDESK_JWT_SECRET_KEY`, `SENTRY_DSN` (optional), `CODESIGN_CERT` (or instructions to fetch it during CI), `CODESIGN_CERT_PASS`.

8) Operational runbook
  - Backup DB file regularly (schedule daily backups to `TRADEDESK_BACKUP_DIR`).
  - Create monitoring alerts for error rate spikes and availability checks hitting `/health`.

9) Quick safety checklist before first production deploy
  - Set environment to production and ensure `TRADEDESK_DEBUG=false`.
  - Run migrations: `python -m tradedesk.backend.cli --init-db`.
  - Verify `/health` returns `{"status":"ok"}`.
  - Start the packaged installer and verify the app launches and backend is reachable.

If you'd like, I can now:
  - Add Sentry initialization (already added in backend), and provide instructions to add `TRADEDESK_SENTRY_DSN` to CI.
  - Create a sample GitHub Actions secret setup snippet and example commands for code-signing.
