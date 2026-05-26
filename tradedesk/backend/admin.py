from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header, Request, Response, Form
from pathlib import Path
import secrets
from typing import List
from .config import settings
from fastapi.responses import HTMLResponse
import hmac
import hashlib
import time
import sqlite3
import json

router = APIRouter()


def _ensure_storage_dir() -> Path:
    target = Path(settings.diagnostics_storage_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "installs").mkdir(exist_ok=True)
    return target


@router.get("/installs")
def list_installs(x_admin_key: str | None = Header(None)) -> List[dict]:
    if not settings.diagnostics_admin_key or x_admin_key != settings.diagnostics_admin_key:
        raise HTTPException(status_code=403)
    storage = _ensure_storage_dir()
    installs = []
    for p in (storage / "installs").iterdir():
        if p.suffix == ".secret":
            installs.append({"install_id": p.stem, "path": str(p)})
    return installs


@router.post("/installs/{install_id}/revoke")
def revoke_install(install_id: str, x_admin_key: str | None = Header(None)) -> dict:
    if not settings.diagnostics_admin_key or x_admin_key != settings.diagnostics_admin_key:
        raise HTTPException(status_code=403)
    storage = _ensure_storage_dir()
    secret_path = storage / "installs" / f"{install_id}.secret"
    if secret_path.exists():
        secret_path.unlink()
    return {"revoked": True}


@router.get("/ui", response_class=HTMLResponse)
def admin_ui(request: Request) -> str:
    # session cookie check (signed)
    cookie = request.cookies.get("diagnostics_admin")
    def _verify_cookie(token: str) -> bool:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False
            payload_b64, expires_str, sig = parts
            msg = f"{payload_b64}.{expires_str}".encode("utf-8")
            expected = hmac.new(settings.jwt_secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                return False
            if int(expires_str) < int(time.time()):
                return False
            return True
        except Exception:
            return False

    if not cookie or not _verify_cookie(cookie):
        # render login form
        return HTMLResponse("""
            <html><body>
            <h2>Admin Login</h2>
            <form method="post" action="/diagnostics/admin/login">
              <label>Admin Key: <input type="password" name="admin_key"/></label>
              <button type="submit">Login</button>
            </form>
            </body></html>
        """)
    storage = _ensure_storage_dir()
    rows = []
    for p in (storage / "installs").iterdir():
        if p.suffix == ".secret":
            rotate_action = f"/diagnostics/admin/installs/{p.stem}/rotate"
            revoke_action = f"/diagnostics/admin/installs/{p.stem}/revoke"
            actions = (
                f"<form method=\"post\" action=\"{rotate_action}\"> <button>Rotate</button></form>"
                f"<form method=\"post\" action=\"{revoke_action}\"> <button>Revoke</button></form>"
            )
            rows.append(f"<tr><td>{p.stem}</td><td>{p.name}</td><td>{actions}</td></tr>")
    html = f"""
    <html><body>
    <h2>Diagnostics Installs</h2>
    <table border="1"><tr><th>Install ID</th><th>Secret File</th><th>Actions</th></tr>{''.join(rows)}</table>
    </body></html>
    """
    return HTMLResponse(html)



@router.post("/login")
def admin_login(response: Response, admin_key: str = Form(...)) -> Response:
    if not settings.diagnostics_admin_key or admin_key != settings.diagnostics_admin_key:
        raise HTTPException(status_code=403)
    # create signed cookie: payload (static), expiry, signature
    expires = int(time.time()) + settings.diagnostics_admin_session_ttl_seconds
    payload_b64 = "admin"
    msg = f"{payload_b64}.{expires}".encode("utf-8")
    sig = hmac.new(settings.jwt_secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    token = f"{payload_b64}.{expires}.{sig}"
    response = HTMLResponse("<html><body>Logged in. <a href=\"/diagnostics/admin/ui\">Continue</a></body></html>")
    response.set_cookie("diagnostics_admin", token, httponly=True, path="/diagnostics/admin", max_age=settings.diagnostics_admin_session_ttl_seconds)
    return response


@router.post("/installs/{install_id}/rotate")
def rotate_install(install_id: str, request: Request) -> dict:
    cookie = request.cookies.get("diagnostics_admin")
    if not cookie:
        raise HTTPException(status_code=403)
    # verify token
    parts = cookie.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=403)
    payload_b64, expires_str, sig = parts
    msg = f"{payload_b64}.{expires_str}".encode("utf-8")
    expected = hmac.new(settings.jwt_secret_key.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig) or int(expires_str) < int(time.time()):
        raise HTTPException(status_code=403)
    storage = _ensure_storage_dir()
    secret_path = storage / "installs" / f"{install_id}.secret"
    new_secret = secrets.token_hex(32)
    with secret_path.open("w", encoding="utf-8") as fh:
        fh.write(new_secret)
    return {"install_id": install_id, "install_secret": new_secret}



@router.get("/audit/export")
def export_audit(x_admin_key: str | None = Header(None)) -> Response:
    """Export audit logs as a JSON array. Protected by diagnostics_admin_key."""
    if not settings.diagnostics_admin_key or x_admin_key != settings.diagnostics_admin_key:
        raise HTTPException(status_code=403)

    dbp = Path(settings.db_path)
    if not dbp.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        conn = sqlite3.connect(str(dbp))
        cur = conn.cursor()
        cur.execute("SELECT id, user_id, action_type, table_name, record_id, old_value, new_value, ip_address, action_time FROM audit_logs ORDER BY action_time ASC")
        rows = cur.fetchall()
        records = []
        for r in rows:
            records.append(
                {
                    "id": r[0],
                    "user_id": r[1],
                    "action_type": r[2],
                    "table_name": r[3],
                    "record_id": r[4],
                    "old_value": json.loads(r[5]) if r[5] else None,
                    "new_value": json.loads(r[6]) if r[6] else None,
                    "ip_address": r[7],
                    "action_time": r[8],
                }
            )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    payload = json.dumps(records, default=str, ensure_ascii=False).encode("utf-8")
    sig = ""
    if settings.diagnostics_admin_key:
        sig = hmac.new(settings.diagnostics_admin_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    headers = {"X-Audit-Signature": sig} if sig else {}
    return Response(content=payload, media_type="application/json", headers=headers)
