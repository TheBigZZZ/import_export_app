from __future__ import annotations

import argparse
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
from PySide6.QtWidgets import QApplication, QCheckBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout

try:
    from .mainwindow import MainWindow
    from .connection_settings import ConnectionSettings, clear_connection_settings, load_connection_settings, save_connection_settings
except ImportError:
    from frontend.mainwindow import MainWindow
    from frontend.connection_settings import ConnectionSettings, clear_connection_settings, load_connection_settings, save_connection_settings

BACKEND_PORT = 8742
BACKEND_STARTUP_TIMEOUT_SECONDS = 90
BACKEND_STARTUP_POLL_INTERVAL_SECONDS = 0.5


def _is_truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_backend_target() -> tuple[str, bool, bool]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend-url")
    parser.add_argument("--configure-connection", action="store_true")
    args, _ = parser.parse_known_args(sys.argv[1:])

    backend_url = (args.backend_url or os.environ.get("TRADEDESK_BACKEND_URL") or "").strip()
    if backend_url:
        if "://" not in backend_url:
            backend_url = f"http://{backend_url}"
        return backend_url.rstrip("/"), False, False

    stored = load_connection_settings()
    if stored and not args.configure_connection and not os.environ.get("TRADEDESK_CONFIGURE_CONNECTION"):
        backend_url = stored.backend_url.strip()
        if backend_url:
            if "://" not in backend_url:
                backend_url = f"http://{backend_url}"
            is_local = backend_url.startswith("http://127.0.0.1") or backend_url.startswith("http://localhost")
            return backend_url.rstrip("/"), is_local, False

    if _is_truthy(os.environ.get("TRADEDESK_HEADLESS_SMOKE")):
        return f"http://127.0.0.1:{BACKEND_PORT}", True, False

    return f"http://127.0.0.1:{BACKEND_PORT}", True, True


class ConnectionSetupDialog(QDialog):
    def __init__(self, initial_backend_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Connection Setup")
        self.setModal(True)

        intro = QLabel(
            "Choose how this desktop connects to TradeDesk. Local mode starts a backend on this PC. Shared mode points all PCs to one backend host on your network."
        )
        intro.setWordWrap(True)

        guidance = QLabel(
            "For a free shared setup, keep one office PC always on, run the backend there, and enter that machine's LAN IP address here."
        )
        guidance.setWordWrap(True)
        guidance.setObjectName("mutedLabel")

        self.backend_url = QLineEdit(initial_backend_url)
        self.backend_url.setPlaceholderText("http://127.0.0.1:8742 or http://192.168.1.50:8742")
        self.remember = QCheckBox("Remember this connection on this PC")
        self.remember.setChecked(True)

        self.help_button = QPushButton("Setup Help")
        self.help_button.clicked.connect(self._show_help)

        self.local_button = QPushButton("Use Local Backend")
        self.local_button.clicked.connect(self._use_local)
        self.shared_button = QPushButton("Use Shared Backend")
        self.shared_button.clicked.connect(self._accept_shared)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.help_button)
        buttons.addStretch(1)
        buttons.addWidget(self.local_button)
        buttons.addWidget(self.shared_button)
        buttons.addWidget(self.cancel_button)

        form = QFormLayout()
        form.addRow("Backend URL", self.backend_url)
        form.addRow("", self.remember)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(guidance)
        layout.addLayout(form)
        layout.addLayout(buttons)

    def _show_help(self) -> None:
        dialog = SetupHelpDialog(self)
        dialog.exec()

    def _use_local(self) -> None:
        self.backend_url.setText(f"http://127.0.0.1:{BACKEND_PORT}")
        self.accept()

    def _accept_shared(self) -> None:
        if not self.backend_url.text().strip():
            QMessageBox.warning(self, "Connection Setup", "Enter a backend URL first, or choose Use Local Backend.")
            return
        self.accept()

    def selected_settings(self) -> ConnectionSettings:
        backend_url = self.backend_url.text().strip()
        if "//" not in backend_url:
            backend_url = f"http://{backend_url}"
        return ConnectionSettings(backend_url=backend_url.rstrip("/"), remember=self.remember.isChecked())


class SetupHelpDialog(QDialog):
        def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("TradeDesk Setup Guide")
                self.setModal(True)
                self.resize(720, 520)

                text = QTextBrowser()
                text.setOpenExternalLinks(True)
                text.setHtml(
                        """
                        <h2>Setup Options</h2>
                        <p><b>Local mode</b>: this PC starts its own backend on <code>127.0.0.1:8742</code>. Use this for single-machine testing.</p>
                        <p><b>LAN mode</b>: one office PC runs the backend and every client uses that PC's LAN IP, for example <code>http://192.168.1.50:8742</code>.</p>
                        <p><b>Online tunnel</b>: a tunnel service gives the host machine a public HTTPS URL. Every client uses that HTTPS URL instead of a LAN address.</p>
                        <p><b>Public host</b>: a VPS or cloud host runs the backend and exposes a public URL directly.</p>
                        <h3>Recommended free options</h3>
                        <ol>
                            <li>LAN host on one always-on office PC.</li>
                            <li>Free tunnel from that PC if you need internet access.</li>
                        </ol>
                        <h3>What to enter in this app</h3>
                        <ul>
                            <li>Local mode: leave the default localhost address.</li>
                            <li>LAN mode: enter the host PC's LAN IP address and port.</li>
                            <li>Online tunnel: enter the public HTTPS URL from the tunnel or host.</li>
                        </ul>
                        <p>The app remembers the chosen backend URL on this computer unless you turn that off.</p>
                        """
                )

                buttons = QHBoxLayout()
                close_button = QPushButton("Close")
                close_button.clicked.connect(self.accept)
                buttons.addStretch(1)
                buttons.addWidget(close_button)

                layout = QVBoxLayout(self)
                layout.addWidget(text)
                layout.addLayout(buttons)


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


def wait_for_backend(backend_url: str) -> None:
    for _ in range(int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)):
        try:
            httpx.get(f"{backend_url}/health", timeout=1.0)
            return
        except Exception:
            time.sleep(BACKEND_STARTUP_POLL_INTERVAL_SECONDS)

    raise RuntimeError(f"Backend not reachable at {backend_url}")


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

    app = QApplication(sys.argv)

    backend_url, should_start_local, should_prompt = _resolve_backend_target()

    if should_prompt or os.environ.get("TRADEDESK_CONFIGURE_CONNECTION") or "--configure-connection" in sys.argv[1:]:
        dialog = ConnectionSetupDialog(backend_url)
        if dialog.exec() == QDialog.Accepted:
            chosen = dialog.selected_settings()
            backend_url = chosen.backend_url
            should_start_local = backend_url.startswith("http://127.0.0.1") or backend_url.startswith("http://localhost")
            if chosen.remember:
                save_connection_settings(chosen)
            else:
                clear_connection_settings()
        else:
            return 0

    backend_proc = start_backend(project_root) if should_start_local else None

    if not should_start_local:
        try:
            wait_for_backend(backend_url)
        except Exception as exc:
            QMessageBox.critical(None, "Backend Unavailable", str(exc))
            return 1

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

    window = MainWindow(backend_url=backend_url)
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
    if backend_proc is not None:
        stop_backend(backend_proc)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
