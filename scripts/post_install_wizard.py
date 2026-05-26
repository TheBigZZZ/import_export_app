from __future__ import annotations

import getpass
import sys

from tradedesk.backend.utils.secret_store import set_secret


def prompt_secret(name: str, hide: bool = True) -> str | None:
    try:
        if hide:
            val = getpass.getpass(f"{name}: ")
        else:
            val = input(f"{name}: ")
    except Exception:
        return None
    return val.strip() or None


def main() -> int:
    print("TradeDesk Post-install Wizard")
    print("Press Enter to skip any value and keep unset.")

    smtp_host = input("SMTP Host (e.g. smtp.example.com): ").strip() or None
    smtp_port = input("SMTP Port (e.g. 587): ").strip() or None
    smtp_user = input("SMTP User (username/email): ").strip() or None
    smtp_pass = prompt_secret("SMTP Password")

    if smtp_host:
        set_secret("diagnostics_smtp_host", smtp_host)
    if smtp_port:
        set_secret("diagnostics_smtp_port", smtp_port)
    if smtp_user:
        set_secret("diagnostics_smtp_user", smtp_user)
    if smtp_pass:
        set_secret("diagnostics_smtp_password", smtp_pass)

    sms_provider = input("SMS Provider (leave blank for none, 'twilio' to enable): ").strip() or None
    if sms_provider:
        set_secret("sms_provider", sms_provider)
        if sms_provider.lower() == "twilio":
            tw_sid = input("Twilio Account SID: ").strip() or None
            tw_token = prompt_secret("Twilio Auth Token")
            from_number = input("Twilio From Number (+123...): ").strip() or None
            if tw_sid:
                set_secret("sms_twilio_account_sid", tw_sid)
            if tw_token:
                set_secret("sms_twilio_auth_token", tw_token)
            if from_number:
                set_secret("sms_from_number", from_number)

    print("Post-install wizard complete. Secrets stored in OS keyring or encrypted file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
