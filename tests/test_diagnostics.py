import asyncio
import json
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from tradedesk.backend.main import app
from tradedesk.backend import config


@pytest_asyncio.fixture
async def client(tmp_path: Path):
    # Configure settings for diagnostics
    original = dict(
        diagnostics_enabled=config.settings.diagnostics_enabled,
        diagnostics_storage_dir=config.settings.diagnostics_storage_dir,
        diagnostics_allow_self_register=config.settings.diagnostics_allow_self_register,
    )
    config.settings.diagnostics_enabled = True
    config.settings.diagnostics_allow_self_register = True
    config.settings.diagnostics_storage_dir = tmp_path

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # restore
    config.settings.diagnostics_enabled = original["diagnostics_enabled"]
    config.settings.diagnostics_allow_self_register = original["diagnostics_allow_self_register"]
    config.settings.diagnostics_storage_dir = original["diagnostics_storage_dir"]


@pytest.mark.asyncio
async def test_register_and_upload(client: httpx.AsyncClient, tmp_path: Path):
    # Register
    r = await client.post("/diagnostics/register", data={})
    assert r.status_code == 200
    body = r.json()
    install_id = body["install_id"]
    secret = body["install_secret"]
    assert install_id and secret

    # Upload with signature
    sample = b"traceback: example" 
    import hmac
    from datetime import datetime, timezone
    import uuid

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    payload = f"{timestamp}\n{nonce}\n".encode("utf-8") + sample
    sig = hmac.new(secret.encode("utf-8"), payload, "sha256").hexdigest()

    files = {"file": ("err.txt", sample, "text/plain")}
    headers = {"X-Install-Id": install_id, "X-Signature": sig, "X-Signature-Timestamp": timestamp, "X-Signature-Nonce": nonce}
    up = await client.post("/diagnostics/upload", files=files, headers=headers)
    assert up.status_code == 200
    assert (tmp_path / next(tmp_path.iterdir()).name)  # some file exists