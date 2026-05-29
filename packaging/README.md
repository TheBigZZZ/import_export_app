# Packaging instructions

1. Ensure you have the project virtualenv active and `pyinstaller` installed:

```powershell
.venv\Scripts\Activate.ps1
pip install pyinstaller
```

1. Build the Windows bundle and run the canonical smoke test:

```powershell
./scripts/build_windows.ps1
./scripts/smoke_test.ps1 -ExePath .\dist\TradeDeskERP\TradeDeskERP.exe -Timeout 180
```

1. The produced exe will be in `dist\TradeDeskERP\TradeDeskERP.exe` (on Windows). Run it to launch the bundled backend and frontend.

Notes:

- The build script uses `packaging/tradedesk.spec` as the entrypoint and bundles the backend and frontend together.
- Code signing is not part of the current release scope.
- This packaging approach bundles Python and required modules; validate the exe with the smoke script before distribution.

## Phase 6 Packaging Guide

This folder contains the production packaging assets for Windows.

### Build Desktop Bundle (PyInstaller)

From workspace root:

```powershell
./scripts/build_windows.ps1
```

Output directory:

```text
dist/TradeDeskERP/
```

### Build Installer (Inno Setup)

1. Install Inno Setup.
2. Open `packaging/TradeDeskERP.iss` in Inno Setup Compiler.
3. Build the installer.

Output installer:

```text
dist/TradeDeskERP-Setup.exe
```

### Notes

- The executable launches the backend and desktop frontend together.
- Runtime data is stored under `%USERPROFILE%/TradeDesk`.
- The Inno Setup installer now includes a TradeDesk-specific deployment page that seeds the first launch connection mode.
- The Inno Setup uninstaller now offers an option to remove the full `%USERPROFILE%/TradeDesk` data tree in addition to the app install folder.
- Re-run `alembic upgrade head` before packaging if database schema changed.

### Diagnostics and Installer

- The installer now includes `.env.production.example` in the application folder so operators can edit runtime settings after install.
- Set these diagnostics variables:

  - `TRADEDESK_DIAGNOSTICS_ENABLED=true`
  - `TRADEDESK_DIAGNOSTICS_ALLOW_SELF_REGISTER=false`
  - `TRADEDESK_DIAGNOSTICS_ADMIN_KEY` (set to a strong secret for admin API/UI)
  - `TRADEDESK_DIAGNOSTICS_UPLOAD_URL` (public URL for uploads)
  - `TRADEDESK_DIAGNOSTICS_WEBHOOK_URL` (optional webhook for notifications)
  - `TRADEDESK_DIAGNOSTICS_NOTIFY_VIA_EMAIL` and SMTP details if using email alerts

The packaged desktop client will use `TRADEDESK_DIAGNOSTICS_UPLOAD_URL_LOCAL` if set, otherwise `TRADEDESK_DIAGNOSTICS_UPLOAD_URL`.
