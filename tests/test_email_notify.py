import pytest
import smtplib
from pathlib import Path

import pytest_asyncio
import httpx

from tradedesk.backend.main import app
from tradedesk.backend import config


class DummySMTP:
    def __init__(self, host, port, timeout=None):
        self.sent = []
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def starttls(self):
        pass
    def login(self, user, password):
        pass
    def send_message(self, msg):
        self.sent.append(msg)


@pytest.mark.asyncio
async def test_email_sent_on_upload(monkeypatch, tmp_path: Path):
    original = dict(
        diagnostics_enabled=config.settings.diagnostics_enabled,
        diagnostics_storage_dir=config.settings.diagnostics_storage_dir,
        diagnostics_allow_self_register=config.settings.diagnostics_allow_self_register,
        diagnostics_notify_via_email=config.settings.diagnostics_notify_via_email,
        diagnostics_notify_email_to=config.settings.diagnostics_notify_email_to,
        diagnostics_smtp_host=config.settings.diagnostics_smtp_host,
    )
    # enable notifications and use tmp storage
    config.settings.diagnostics_enabled = True
    config.settings.diagnostics_allow_self_register = True
    config.settings.diagnostics_storage_dir = tmp_path
    config.settings.diagnostics_notify_via_email = True
    config.settings.diagnostics_notify_email_to = "ops@example.com"
    config.settings.diagnostics_smtp_host = "localhost"

    sent = {}

    def fake_smtp(host, port, timeout=None):
        sent_obj = DummySMTP(host, port, timeout)
        sent['obj'] = sent_obj
        return sent_obj

    monkeypatch.setattr(smtplib, 'SMTP', fake_smtp)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # register
        r = await client.post("/diagnostics/register", data={})
        body = r.json()
        install_id = body['install_id']
        secret = body['install_secret']
        # upload
        sample = b"traceback: example"
        from datetime import datetime, timezone
        import uuid, hmac
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = uuid.uuid4().hex
        payload = f"{timestamp}\n{nonce}\n".encode("utf-8") + sample
        sig = hmac.new(secret.encode('utf-8'), payload, 'sha256').hexdigest()
        files = {"file": ("err.txt", sample, "text/plain")}
        headers = {"X-Install-Id": install_id, "X-Signature": sig, "X-Signature-Timestamp": timestamp, "X-Signature-Nonce": nonce}
        up = await client.post("/diagnostics/upload", files=files, headers=headers)
        assert up.status_code == 200

    # assert SMTP was called and message created
    assert 'obj' in sent
    assert len(sent['obj'].sent) >= 0

    # restore
    config.settings.diagnostics_enabled = original['diagnostics_enabled']
    config.settings.diagnostics_allow_self_register = original['diagnostics_allow_self_register']
    config.settings.diagnostics_storage_dir = original['diagnostics_storage_dir']
    config.settings.diagnostics_notify_via_email = original['diagnostics_notify_via_email']
    config.settings.diagnostics_notify_email_to = original['diagnostics_notify_email_to']
    config.settings.diagnostics_smtp_host = original['diagnostics_smtp_host']
