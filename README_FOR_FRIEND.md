# TradeDesk ERP - Verification & Testing Notes

This release is prepared for your verification. Below are the key features implemented and the exact steps to run and test the app locally.

## Quick Start

Create and activate a virtual environment if you have not already:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Initialize the database if needed:

```powershell
.venv\Scripts\python -m tradedesk.backend.cli --init-db
```

Start the backend:

```powershell
.venv\Scripts\python -m uvicorn tradedesk.backend.main:app --host 127.0.0.1 --port 8742
```

Start the GUI:

```powershell
.venv\Scripts\python -m frontend.main
```

Login with the admin account:

- Username: `admin`
- Password: `TestP@ssw0rd!`

## What to Test

- Users: create a user, delete a single user, and delete multiple users.
- Parties: create customers and suppliers, then verify A/R and A/P show the balance column.
- Vouchers: create a cash or bank voucher after account setup.
- Imports: create import costing entries and post them to allocate costs.
- Inventory: create a product, apply stock movements, and verify the ledger.
- Invoicing: create a sales invoice, generate a PDF, and optionally send via SMTP.
- Settings: save company settings, add SMTP credentials, and run `Send Test Email`.
- SMS: verify console logging by default, then configure Twilio for real SMS.
- Exchange rates: create a rate, enable auto-sync, and set the sync interval in minutes.

## Security and Production Checklist

- Change `TRADEDESK_JWT_SECRET_KEY` to a cryptographically secure secret in your environment or config.
- Use HTTPS with a reverse proxy such as nginx or IIS in production.
- Secure DB backups and rotate them; do not leave the DB on a user desktop.
- Use strong SMTP credentials and consider encrypted storage for the SMTP password.
- Set `max_users` to the correct number for your deployment and review role assignments.
- Configure a reliable exchange-rate provider or a paid API for SLA needs.
- Integrate a real SMS provider and secure its credentials.
- Limit CORS, enable firewall rules, and run under a service account.
- Configure production logging and Sentry for error reporting if you use it.

## Notes and Known Limitations

- SMTP password is stored in app settings JSON in plain text unless encrypted storage is enabled.
- Background exchange-rate sync runs only when `exchange_rate_auto_sync` is enabled and the backend is running.
- SMS defaults to console logging unless Twilio is configured and the `twilio` library is installed.

## Files Changed in This Release

- Backend: `tradedesk/backend/*` for roles, settings, email/SMS, and exchange-rate sync.
- Frontend: `frontend/modules/*` for Users, Settings, Customers, and Suppliers, plus `assets/icons/*.svg`.
- Scripts: `scripts/verify_user_flow.py`.

If you want, I can prepare a zip build for your friend or an installer next.
