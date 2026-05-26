from __future__ import annotations

import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, Header
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from .config import settings
import json
import httpx
import smtplib
from email.message import EmailMessage

router = APIRouter()


def _ensure_storage_dir() -> Path:
    target = Path(settings.diagnostics_storage_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "installs").mkdir(exist_ok=True)
    # nonces dir (optional)
    nonces = Path(settings.diagnostics_nonces_dir) if settings.diagnostics_nonces_dir else (target / "nonces")
    nonces.mkdir(parents=True, exist_ok=True)
    return target


def _upload_enabled() -> bool:
    return bool(settings.diagnostics_enabled)


def _install_secret_path(storage: Path, install_id: str) -> Path:
    return storage / "installs" / f"{install_id}.secret"


@router.post("/register")
async def register_install(
    install_id: Optional[str] = Form(None),
    admin_key: Optional[str] = Form(None),
):
    """Register an install and return an install secret. Registration is only
    allowed if diagnostics_allow_self_register is True or the correct
    diagnostics_admin_key is provided.
    """
    if not (settings.diagnostics_allow_self_register or (admin_key and admin_key == settings.diagnostics_admin_key)):
        raise HTTPException(status_code=403, detail="Registration disabled")

    if not install_id:
        install_id = uuid.uuid4().hex

    storage = _ensure_storage_dir()
    secret = secrets.token_hex(32)
    path = _install_secret_path(storage, install_id)
    try:
        with path.open("w", encoding="utf-8") as fh:
            fh.write(secret)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to persist install secret")

    return {"install_id": install_id, "install_secret": secret}


def _verify_signature(storage: Path, install_id: str, signature: str, payload: bytes) -> bool:
    path = _install_secret_path(storage, install_id)
    if not path.exists():
        return False
    try:
        secret = path.read_text(encoding="utf-8").strip()
    except Exception:
        return False
    # signature expected as hex of HMAC-SHA256
    mac = hmac.new(secret.encode("utf-8"), payload, "sha256").hexdigest()
    return hmac.compare_digest(mac, signature)


def _verify_signature_with_headers(storage: Path, install_id: str, signature: str, timestamp: Optional[str], nonce: Optional[str], body: bytes) -> bool:
    # If timestamp/nonce provided, reconstruct payload and check skew
    # Expect timestamp like 2026-05-25T12:34:56Z
    if timestamp and nonce:
        try:
            ts_dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return False
        # check skew
        skew = abs((datetime.now(timezone.utc) - ts_dt).total_seconds())
        if skew > settings.diagnostics_signature_skew_seconds:
            return False
        # Check and persist nonce to prevent replay
        nonces_dir = Path(settings.diagnostics_nonces_dir) if settings.diagnostics_nonces_dir else (storage / "nonces")
        nonces_dir.mkdir(parents=True, exist_ok=True)
        nonce_path = nonces_dir / nonce
        try:
            # atomic creation: fail if exists
            fd = os.open(str(nonce_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return False
        except Exception:
            # if we can't persist nonce, fail closed
            return False
        payload = f"{timestamp}\n{nonce}\n".encode("utf-8") + body
        return _verify_signature(storage, install_id, signature, payload)
    # fallback: legacy behavior — sign body only
    return _verify_signature(storage, install_id, signature, body)


def purge_old_diagnostics() -> None:
    """Remove diagnostics files older than configured retention days."""
    storage = Path(settings.diagnostics_storage_dir)
    if not storage.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.diagnostics_retention_days)
    for p in storage.iterdir():
        try:
            if p.is_file():
                mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
                if mtime < cutoff:
                    p.unlink()
        except Exception:
            # ignore individual failures
            continue
    # purge nonces older than TTL
    nonces_dir = Path(settings.diagnostics_nonces_dir) if settings.diagnostics_nonces_dir else (storage / "nonces")
    if nonces_dir.exists():
        nonce_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.diagnostics_nonces_ttl_days)
        for n in nonces_dir.iterdir():
            try:
                if n.is_file():
                    mtime = datetime.fromtimestamp(n.stat().st_mtime, timezone.utc)
                    if mtime < nonce_cutoff:
                        n.unlink()
            except Exception:
                continue


@router.post("/upload")
async def upload_diagnostics(
    file: UploadFile = File(...),
    contact_email: str | None = Form(None),
    description: str | None = Form(None),
    x_install_id: Optional[str] = Header(None),
    x_signature: Optional[str] = Header(None),
    x_signature_timestamp: Optional[str] = Header(None),
    x_signature_nonce: Optional[str] = Header(None),
    enabled: bool = Depends(_upload_enabled),
):
    if not enabled:
        raise HTTPException(status_code=404, detail="Diagnostics upload disabled")

    content = await file.read()
    if len(content) > settings.diagnostics_max_bytes:
        raise HTTPException(status_code=413, detail="File too large")

    storage = _ensure_storage_dir()

    # If install headers are provided, verify HMAC signature. Support timestamp+nonce.
    if x_install_id and x_signature:
        ok = _verify_signature_with_headers(storage, x_install_id, x_signature, x_signature_timestamp, x_signature_nonce, content)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid signature")

    ticket = uuid.uuid4().hex
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = Path(file.filename).name
    filename = f"{ts}-{ticket}-{safe_name}"
    path = storage / filename
    try:
        with path.open("wb") as fh:
            fh.write(content)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to store file")

    # Optionally write metadata
    meta_path = storage / f"{ticket}.meta"
    try:
        with meta_path.open("w", encoding="utf-8") as mh:
            mh.write(f"received={ts}\n")
            mh.write(f"original_filename={safe_name}\n")
            mh.write(f"contact_email={contact_email or ''}\n")
            mh.write(f"description={description or ''}\n")
            if x_install_id:
                mh.write(f"install_id={x_install_id}\n")
    except Exception:
        # non-fatal
        pass

    # Notify webhook if configured (best-effort)
    try:
        if settings.diagnostics_webhook_url:
            payload = {
                "ticket": ticket,
                "received": ts,
                "original_filename": safe_name,
                "install_id": x_install_id,
                "contact_email": contact_email,
                "description": description,
            }
            with httpx.Client(timeout=5.0) as client:
                client.post(settings.diagnostics_webhook_url, json=payload)
    except Exception:
        pass

    # Optionally send email notification
    try:
        if settings.diagnostics_notify_via_email and settings.diagnostics_notify_email_to:
            msg = EmailMessage()
            msg["From"] = settings.diagnostics_notify_email_from or "noreply@example.com"
            msg["To"] = settings.diagnostics_notify_email_to
            msg["Subject"] = f"New diagnostics upload: {ticket}"
            body_txt = f"Ticket: {ticket}\nReceived: {ts}\nFile: {safe_name}\nInstall: {x_install_id or ''}\nContact: {contact_email or ''}\nDescription: {description or ''}\n"
            msg.set_content(body_txt)
            try:
                with smtplib.SMTP(settings.diagnostics_smtp_host or "localhost", settings.diagnostics_smtp_port, timeout=10) as smtp:
                    if settings.diagnostics_smtp_user and settings.diagnostics_smtp_password:
                        smtp.starttls()
                        smtp.login(settings.diagnostics_smtp_user, settings.diagnostics_smtp_password)
                    smtp.send_message(msg)
            except Exception:
                # swallow email errors
                pass
    except Exception:
        pass

    return {"ticket": ticket, "received": True}
