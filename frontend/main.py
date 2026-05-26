from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import uuid
from datetime import datetime, timezone

import httpx
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog

try:
    from .mainwindow import MainWindow
except ImportError:
    from frontend.mainwindow import MainWindow

BACKEND_PORT = 8742
BACKEND_STARTUP_TIMEOUT_SECONDS = 90
BACKEND_STARTUP_POLL_INTERVAL_SECONDS = 0.5


def _run_backend_server() -> None:
    import tempfile

    tmp = Path(tempfile.gettempdir()) / "tradedesk-backend-error.txt"
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:
        pass

    # Launch the backend as a separate process via the frozen executable's
    # dedicated backend mode. This is more reliable than multiprocessing spawn
    # on Windows CI runners.
    backend_cmd = [
        sys.executable,
        "--backend-cli",
        "--serve",
    ]
    log_path = Path(tempfile.gettempdir()) / "tradedesk-backend.log"
    log_file = open(log_path, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            backend_cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path(sys.executable).parent),
        )
        for _ in range(int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)):
            try:
                httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1.0)
                return proc
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(f"Backend exited early with code {proc.returncode}; see {log_path}")
                time.sleep(BACKEND_STARTUP_POLL_INTERVAL_SECONDS)
        raise RuntimeError(f"Backend failed to start; see {log_path}")
    finally:
        try:
            log_file.close()
        except Exception:
            pass


def start_backend(project_root: Path) -> Any:
    if getattr(sys, "frozen", False):
        return _run_backend_server()

    env = dict(**os.environ)
    env["PYTHONPATH"] = str(project_root)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tradedesk.backend.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(BACKEND_PORT),
            "--no-access-log",
        ],
        cwd=str(project_root),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)):
        try:
            httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1.0)
            return proc
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError(f"Backend exited early with code {proc.returncode}")
            time.sleep(BACKEND_STARTUP_POLL_INTERVAL_SECONDS)

    proc.terminate()
    raise RuntimeError("Backend failed to start")


def stop_backend(proc: Any) -> None:
    proc.terminate()
    if hasattr(proc, "wait"):
        proc.wait(timeout=3)
    else:
        proc.join(timeout=3)


def load_styles(app: QApplication, project_root: Path) -> None:
    qss_path = project_root / "frontend" / "assets" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    if getattr(sys, "frozen", False):
        project_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        project_root = Path(__file__).resolve().parents[1]

    backend_proc = start_backend(project_root)

    app = QApplication(sys.argv)
    load_styles(app, project_root)

    # If a diagnostic traceback file exists from a previous run, offer the
    # user the option to upload it to a secure endpoint for debugging.
    try:
        import tempfile

        tmp = Path(tempfile.gettempdir()) / "tradedesk-backend-error.txt"
        upload_url = os.environ.get("TRADEDESK_DIAGNOSTICS_UPLOAD_URL") or os.environ.get("TRADEDESK_DIAGNOSTICS_UPLOAD_URL_LOCAL")
        if tmp.exists() and upload_url:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Send Diagnostic Report")
            msg.setText(
                "The application detected an error report from a previous run. \nWould you like to upload it to the support server to help diagnose the problem?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            res = msg.exec()
            if res == QMessageBox.Yes:
                email, ok = QInputDialog.getText(None, "Contact Email (optional)", "Email:")
                description, _ = QInputDialog.getText(None, "Description (optional)", "Describe what you were doing:")
                try:
                    import httpx
                    import hashlib
                    import hmac
                    import json

                    files = {"file": (tmp.name, tmp.open("rb"), "text/plain")}
                    data = {}
                    if ok and email:
                        data["contact_email"] = email
                    if description:
                        data["description"] = description

                    # Attempt to load local install secret if present; if not,
                    # try to self-register to obtain one (only if server allows it).
                    install_store = Path.home() / "TradeDesk" / "install.json"
                    install_id = None
                    install_secret = None
                    if install_store.exists():
                        try:
                            obj = json.loads(install_store.read_text(encoding="utf-8"))
                            install_id = obj.get("install_id")
                            install_secret = obj.get("install_secret")
                        except Exception:
                            install_id = None

                    if not install_id:
                        # Try self-register
                        try:
                            with httpx.Client(timeout=10.0) as client:
                                resp = client.post(upload_url.replace("/upload", "/register"), data={})
                            if resp.status_code == 200:
                                body = resp.json()
                                install_id = body.get("install_id")
                                install_secret = body.get("install_secret")
                                if install_id and install_secret:
                                    install_store.parent.mkdir(parents=True, exist_ok=True)
                                    install_store.write_text(json.dumps({"install_id": install_id, "install_secret": install_secret}))
                        except Exception:
                            # registration failed; continue without signing
                            install_id = None
                            install_secret = None

                    # If we have an install secret, compute signature and include headers (timestamp + nonce)
                    headers = {}
                    body_bytes = tmp.read_bytes()
                    if install_id and install_secret:
                        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        nonce = uuid.uuid4().hex
                        payload = f"{timestamp}\n{nonce}\n".encode("utf-8") + body_bytes
                        mac = hmac.new(install_secret.encode("utf-8"), payload, "sha256").hexdigest()
                        headers["X-Install-Id"] = install_id
                        headers["X-Signature"] = mac
                        headers["X-Signature-Timestamp"] = timestamp
                        headers["X-Signature-Nonce"] = nonce

                    # Use httpx to post with headers
                    with httpx.Client(timeout=15.0) as client:
                        resp = client.post(upload_url, files={"file": (tmp.name, body_bytes, "text/plain")}, data=data, headers=headers)

                    if resp.status_code == 200:
                        QMessageBox.information(None, "Uploaded", f"Diagnostic uploaded. Ticket: {resp.json().get('ticket')}" )
                        try:
                            tmp.unlink()
                        except Exception:
                            pass
                    else:
                        QMessageBox.warning(None, "Upload Failed", f"Server returned: {resp.status_code}")
                except Exception as exc:
                    QMessageBox.warning(None, "Upload Failed", str(exc))
    except Exception:
        # keep UI responsive if diagnostics flow fails
        pass

    window = MainWindow(backend_url=f"http://127.0.0.1:{BACKEND_PORT}")
    # Check for updates (if configured) before showing main window
    try:
        from .update_checker import check_for_update

        current_version = os.environ.get("TRADEDESK_VERSION", "0.1.0")
        try:
            check_for_update(None, current_version)
        except Exception:
            # Fail silently - update checks must not block startup
            pass
    except Exception:
        pass

    window.show()

    exit_code = app.exec()
    stop_backend(backend_proc)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
