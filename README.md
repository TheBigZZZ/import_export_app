# TradeDesk ERP

TradeDesk ERP is a desktop ERP that can run locally for development or connect to a shared live backend for multi-user use.

## Stack

- Backend: FastAPI + SQLAlchemy (async) + SQLite for local/dev, with support for a shared database URL in live mode
- Frontend: PySide6 desktop client
- Auth: JWT with bcrypt password hashing
- Live sync: Server-sent events from the backend to refresh open clients automatically
- Reporting stack prepared with pandas, OpenPyXL, and ReportLab

## Current Status

This repository is implemented through **Phase 6 (Packaging + Installer Assets)**:

- Project structure
- SQLAlchemy models for all core tables
- Alembic baseline migration
- JWT auth, lockout rules, and user CRUD foundation
- PySide6 shell with sidebar + stacked modules
- Backend launcher from frontend app
- Service-layer business rule utilities + unit tests
- Chart of accounts API (list, create, update, tree, ledger)
- Voucher API (list/create/get/update/void with double-entry enforcement)
- Cash API (receipt/payment posting and daily closing)
- Bank API (bank account CRUD baseline, bank transfer, statements)
- Customer API (CRUD + customer ledger)
- Supplier API (CRUD + supplier ledger)
- Product API (CRUD + stock movement posting + product stock ledger)
- Stock update rules enforced (posted-only document + negative stock prevention unless allowed)
- SQLAlchemy audit listeners registered for core models
- Sales, purchase, and import posting operations with voucher + stock integration
- Expenses module with voucher-linked posting
- Dashboard KPIs, trial balance, stock position, and profit/loss report endpoints
- Settings API for company profile and negative-stock toggle persistence
- Backup/restore API for SQLite database snapshots
- Desktop modules for Dashboard, Expenses, Reports, and Settings
- Packaging artifacts: PyInstaller spec, build script, and Inno Setup installer template

## Quick Start

1. Create and activate a Python 3.12+ virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

Optional: copy environment template and adjust values:

```powershell
Copy-Item .env.example .env
```

1. Run migration:

```powershell
cd tradedesk/backend
alembic upgrade head
cd ../..
```

1. Start desktop app:

```powershell
python -m frontend.main
```

First-run admin setup:

- On a fresh database, the desktop app now shows a first-run admin setup wizard before the login screen.
- Create the initial super-admin in that wizard, then share those credentials only with the trusted owner.
- If you want the app to remember them on that PC, use the wizard's save option or create the admin with `--init-admin` during unattended setup.

Create initial admin via CLI (recommended for installers)

```powershell
# Non-interactive initial admin creation (run after migrations)
python -m tradedesk.backend.cli --init-admin --admin-username admin --admin-password "YourP@ssw0rd" --admin-full-name "Owner Name"
```

To reset a user's password via the CLI:

```powershell
python -m tradedesk.backend.cli --reset-admin-password --target-username admin --admin-password "NewP@ssw0rd"
```

Recommended setup for nontechnical users:

1. Use one always-on host PC.
2. Install TradeDesk on the host PC and choose `Use Local Backend` the first time it opens.
3. Install [Tailscale](https://tailscale.com/download) on the host PC and on every client PC.
4. Sign in to Tailscale on every machine.
5. Use the host PC's Tailscale IP address, usually a `100.x.x.x` address, as the backend URL on client PCs.
6. On each client PC, open TradeDesk and choose `Use Shared Backend`.
7. Enter `http://100.x.x.x:8742` using the host PC's actual Tailscale IP.
8. Leave the connection saved on each client.
9. Test the setup by changing data on one PC and confirming the other PC refreshes automatically.

If you need access from outside the office, use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/) or another HTTPS tunnel on the host PC and enter the public `https://` URL instead of the Tailscale address.

Live/shared deployment details:

- Set `TRADEDESK_BACKEND_URL` on each desktop client to point at the shared backend if you want to configure it by environment variable instead of the in-app dialog.
- Set `TRADEDESK_DATABASE_URL` on the backend to point at a shared database if you want a non-SQLite deployment.
- Leave `TRADEDESK_BACKEND_URL` unset for local single-user development; the desktop app will start its own backend on `127.0.0.1:8742`.
- The first desktop launch shows a connection setup dialog if no client setting exists yet. It stores the chosen backend URL in `~/TradeDesk/client-settings.json`.
- Reopen the dialog later with `--configure-connection` or `TRADEDESK_CONFIGURE_CONNECTION=1`.

## Run Tests

```powershell
pytest -q
```

## Release & Update Manifest

The GitHub Actions workflow `/.github/workflows/release-installer.yml` creates a release artifact and uploads an `updates.json` manifest. The desktop client will check the manifest when `TRADEDESK_UPDATE_MANIFEST_URL` is configured.

Manifest format (JSON):

```json
{
  "version": "v1.2.3",
  "installer_url": "https://github.com/owner/repo/releases/download/v1.2.3/TradeDeskERP-Setup.exe",
  "installer_sha256": "<sha256-hex>",
  "published_at": "2026-05-25T12:00:00Z"
}
```

Set the environment variable `TRADEDESK_UPDATE_MANIFEST_URL` to point to the raw `updates.json` URL in your release or hosting location to enable update checks in the desktop client.

## First-run testing checklist

- Run `python -m tradedesk.backend.cli --init-db` to apply migrations.
- Create initial admin using the CLI as shown above.
- Start the backend and run the smoke test script:

```powershell
# Start backend in one terminal
python -m uvicorn tradedesk.backend.main:app --host 127.0.0.1 --port 8742

# In another terminal, run smoke checks
$env:TRADEDESK_TEST_ADMIN_USER='admin'; $env:TRADEDESK_TEST_ADMIN_PASS='YourP@ssw0rd'; .venv\Scripts\python scripts\ci_smoke_test_no_uvicorn.py
```

Include platform-specific checks:

- Installer: build and run the installer on a clean VM and verify the first-run setup flow (use `--init-admin` in unattended installer steps).
- Auto-update: publish a test release with `updates.json` pointing to the installer and confirm the desktop client prompts and runs the installer (verify checksum externally).

## Local packaged build + installer test (Windows)

```powershell
# Build EXE + installer
.\scripts\build_windows.ps1 -PythonExe .\.venv\Scripts\python.exe -BuildInstaller

# Launch packaged app
Start-Process .\dist\TradeDeskERP\TradeDeskERP.exe

# Health + smoke test against packaged backend
.venv\Scripts\python scripts\check_health.py
$env:TRADEDESK_TEST_ADMIN_USER='admin'; $env:TRADEDESK_TEST_ADMIN_PASS='YourP@ssw0rd'; .venv\Scripts\python scripts\ci_smoke_test_no_uvicorn.py
```

Expected outputs:

- `Health OK`
- `CI smoke test PASSED`

## Production Hardening

- Set `TRADEDESK_ENVIRONMENT=production` in `.env`.
- Set a strong non-default `TRADEDESK_JWT_SECRET_KEY`.
- Keep `TRADEDESK_DEBUG=false` in production.
- Keep `TRADEDESK_BCRYPT_ROUNDS>=12` in production.
- Keep `TRADEDESK_ENFORCE_STARTUP_CHECKS=true` to verify required DB tables exist at startup.
- For multi-user live mode, set `TRADEDESK_BACKEND_URL` on the desktop client and run one shared backend instance for everyone.

## Build Windows App (Phase 6)

```powershell
./scripts/build_windows.ps1
```

For installer build instructions, see:

- `packaging/README.md`

## How to run (developer)

1. Create and activate a virtual environment (Windows PowerShell):

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

1. Copy the environment template and fill required secrets (do NOT commit secrets):

```powershell
Copy-Item .env.production.example .env
# edit .env and set TRADEDESK_JWT_SECRET_KEY, SMTP creds, and DB path
```

1. Initialize DB and run migrations:

```powershell
python -m tradedesk.backend.cli --init-db
```

1. Run tests locally:

```powershell
.venv\Scripts\python -m pytest -q
```

1. Start the desktop app (development):

```powershell
python -m frontend.main
```

## Tests and verification you should run before sharing

- Unit tests: `pytest -q` (already included)
- Smoke test: run the packaged EXE smoke test script (see `scripts/smoke_test.ps1`) after building
- Integration tests: exercise `/health`, auth, create a customer, create an invoice, send invoice email (use a sandbox SMTP)
- Backup/restore: run the backup CLI and restore to a temp DB, verify data integrity

## Packaging & distribution (how to share with a friend)

1. Build the Windows EXE locally using the provided script:

```powershell
.venv\Scripts\python -m pip install pyinstaller==6.20.0
.\scripts\build_windows.ps1 -PythonExe .\.venv\Scripts\python.exe -BuildInstaller
```

1. Optionally sign the EXE using a code signing certificate (recommended). Store your PFX in GitHub Secrets or Key Vault for CI signing.

1. Create an installer (Inno Setup template included under `packaging/`).

1. For quick testing, zip the `dist/TradeDeskERP` folder and share it with instructions to run `TradeDeskERP.exe` after unzip and to configure `.env` from `.env.production.example` using non-production secrets.

## Security hygiene (required before sharing)

- Remove any hard-coded secrets from repo (never commit `.env` with secrets).
- Do not include default admin credentials. Create a one-time setup process or provide an initial admin user creation CLI.
- Use test/sandbox SMTP (Mailtrap) when testing email functionality.

## Performance & concurrency checks

- Run a small load test with `wrk` or `hey` against `/health` and core endpoints to ensure the packaged server can handle expected concurrent users.
- Monitor memory and CPU while exercising typical workflows (invoices, imports, stock updates).

## Notes

- This README intentionally omits default seeded credentials and any sample production secrets. Populate `.env` from `.env.production.example` before running.

## Phase Plan

- Phase 1-4: foundation, accounting, inventory, operational posting
- Phase 5: reporting, dashboard KPIs, settings, backup/restore (completed)
- Phase 6: packaging (PyInstaller + installer assets) (completed)
