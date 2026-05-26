# Packaging instructions

1. Ensure you have the project virtualenv active and `pyinstaller` installed:

```powershell
.venv\Scripts\Activate.ps1
pip install pyinstaller
```

1. Build single-file executable:

```powershell
./packaging/build_exe.ps1
```

1. The produced exe will be in `dist\TradeDesk.exe` (on Windows). Run it to launch the bundled backend and frontend.

Notes:

- The build script uses `launcher.py` as the entrypoint which forwards to `frontend.main`.
- No code-signing is performed. If you later want to sign the binary, provide a code-signing utility and certificate.
- This packaging approach bundles Python and required modules; test the exe on a clean Windows VM before distribution.

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
