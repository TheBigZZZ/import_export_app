TradeDesk ERP - Verification & Testing Notes

This release is prepared for your verification. Below are the key features implemented and exact steps to run and test the app locally.

1) Quick start (Windows, Python virtualenv)

- Create and activate virtualenv (if not already):
  python -m venv .venv
  .venv\Scripts\Activate.ps1
- Install dependencies (if not done):
  pip install -r requirements.txt
- Initialize DB (if needed):
  .venv\Scripts\python -m tradedesk.backend.cli --init-db

- Start backend:
  .venv\Scripts\python -m uvicorn tradedesk.backend.main:app --host 127.0.0.1 --port 8742
- Start GUI:
  .venv\Scripts\python -m frontend.main

- Login with admin:
  username: admin
  password: TestP@ssw0rd!

2) What to test (critical happy paths)
- Users
  - Create a user (up to 3 users allowed total)
  - Delete a single user (select one row, press Delete Selected)
  - Delete multiple users (multi-select + Delete Selected)
- Parties
  - Create Customer / Supplier
  - Validate A/R and A/P show Balance column
  - Delete single / bulk-delete
- Vouchers
  - Create cash/bank voucher (requires account setup)
- Imports
  - Create import costing entries and post to allocate costs
- Inventory
  - Create product, apply stock movements, verify ledger
- Invoicing
  - Create sales invoice, generate PDF (File -> Export), optionally send via SMTP
- Settings
  - Save company settings
  - Add SMTP credentials and `Send Test Email`
  - Test SMS: by default logs to server console; configure Twilio to send real SMS
  - Exchange rates: create a rate and enable `Enable auto-sync exchange rates` and set `Sync Interval` (minutes). The backend will sync on startup and every interval (if enabled).

3) Security & Production checklist (items that must be done before production)
- Change `TRADEDESK_JWT_SECRET_KEY` to a cryptographically secure secret in env or config
- Use HTTPS with a reverse proxy (nginx/IIS/AS) in production
- Secure DB backups and rotate them (don't leave DB on user desktop)
- Use strong SMTP credentials and consider encrypted storage for SMTP password (we can implement keyring or local encryption)
- Set `max_users` to an appropriate number (default 3) and review role assignments
- Configure a reliable exchange-rate provider or subscribe to a paid API for SLAs
- Integrate a real SMS provider and secure credentials (Twilio supported in code)
- Hardening: limit CORS, enable firewall rules, and run under a service account
- Monitoring & logging: configure production logging and Sentry DSN for error reporting

4) Notes & known limitations
- SMTP password stored in app settings JSON (plain text). If needed, enable encrypted storage before production.
- Background exchange-rate sync runs only when `exchange_rate_auto_sync` enabled and backend started; it's a simple loop, not a scheduler.
- SMS defaults to console logging unless Twilio configured and `twilio` lib installed.

5) Files changed in this release
- Backend: tradedesk/backend/* (roles endpoint, settings, email/sms, exchange-rate sync)
- Frontend: frontend/modules/* (Users, Settings, Customers, Suppliers), assets/icons/*.svg
- Scripts: scripts/verify_user_flow.py

If you want, I can create a zip build for you to send to your friend or prepare an installer. Tell me which packaging you prefer (zip, installer, or Docker image) and I will prepare it next.
