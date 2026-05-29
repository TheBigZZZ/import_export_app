from __future__ import annotations

import logging

from ..config import settings

logger = logging.getLogger(__name__)


def send_sms(to_number: str, message: str) -> None:
    """Send SMS using configured provider. Default is console logger.

    If Twilio is configured (sms_provider == 'twilio' and credentials present), attempt to use it.
    """
    provider = (settings.sms_provider or "").lower()
    if provider == "twilio":
        try:
            from twilio.rest import Client
        except Exception:
            raise RuntimeError("twilio library not installed")
        if (
            not settings.sms_twilio_account_sid
            or not settings.sms_twilio_auth_token
            or not settings.sms_from_number
        ):
            raise RuntimeError("Twilio credentials not configured")
        client = Client(settings.sms_twilio_account_sid, settings.sms_twilio_auth_token)
        client.messages.create(
            body=message, from_=settings.sms_from_number, to=to_number
        )
        return

    # default: just log the message (useful for development)
    logger.info("SMS to %s: %s", to_number, message)
    return
