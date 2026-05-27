from __future__ import annotations

import argparse
import json
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
    from .error_messages import friendly_exception_message, friendly_http_error
except ImportError:
    from frontend.mainwindow import MainWindow
    from frontend.connection_settings import ConnectionSettings, clear_connection_settings, load_connection_settings, save_connection_settings
    from frontend.error_messages import friendly_exception_message, friendly_http_error

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
            "Recommended for nontechnical users: use Tailscale so everyone can connect to one host PC without firewall changes or port forwarding."
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
        self.resize(780, 640)

        text = QTextBrowser(self)
        text.setOpenExternalLinks(True)
        text.setHtml(
            """
            <h2>Recommended setup for nontechnical users</h2>
            <p><b>Best simple choice:</b> use <a href="https://tailscale.com/download">Tailscale</a> on one host PC and on every client PC. It lets the app connect to one shared backend without port forwarding, router changes, or static IP setup.</p>
            <p><b>If you need internet access outside the office:</b> use <a href="https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/">Cloudflare Tunnel</a> or another public HTTPS tunnel on the host machine.</p>

            <h3>Option A - Local setup on one PC</h3>
            <ol>
                <li>Install TradeDesk on the PC you want to use as the main machine.</li>
                <li>Open the app and click <b>Use Local Backend</b>.</li>
                <li>Leave the URL as <code>http://127.0.0.1:8742</code>.</li>
                <li>Log in with the admin account.</li>
                <li>Keep that app open; it will start and use the local backend automatically.</li>
            </ol>

            <h3>Option B - Shared setup using Tailscale</h3>
            <ol>
                <li>Pick one always-on PC to act as the host.</li>
                <li>Install TradeDesk on the host PC and open it once.</li>
                <li>On the host PC, click <b>Use Local Backend</b>.</li>
                <li>Install Tailscale on the host PC from <a href="https://tailscale.com/download">tailscale.com/download</a>.</li>
                <li>Sign in to Tailscale on the host PC.</li>
                <li>Install Tailscale on every client PC and sign in with the same Tailscale account or invite those users to your tailnet.</li>
                <li>In the Tailscale admin page, find the host PC's Tailscale IP address, usually starting with <code>100.</code>.</li>
                <li>On each client PC, open TradeDesk and choose <b>Use Shared Backend</b>.</li>
                <li>Enter the Tailscale address exactly, for example <code>http://100.101.102.103:8742</code>.</li>
                <li>Leave <b>Remember this connection</b> checked on each client.</li>
                <li>Log in normally on each client.</li>
            </ol>

            <h3>Option C - Shared setup with a public HTTPS URL</h3>
            <ol>
                <li>Run the backend on a server or always-on machine.</li>
                <li>Set up Cloudflare Tunnel or a similar HTTPS tunnel.</li>
                <li>On each client, choose <b>Use Shared Backend</b>.</li>
                <li>Enter the public HTTPS URL exactly, such as <code>https://trade.example.com</code>.</li>
                <li>Log in after the connection is saved.</li>
            </ol>

            <h3>What to type in the URL field</h3>
            <ul>
                <li><b>Local:</b> <code>http://127.0.0.1:8742</code></li>
                <li><b>Tailscale host:</b> <code>http://100.x.x.x:8742</code></li>
                <li><b>Public host/tunnel:</b> <code>https://...</code></li>
            </ul>

            <h3>Recommended free path</h3>
            <ol>
                <li>Use one office PC as the host.</li>
                <li>Install Tailscale on the host and on every client.</li>
                <li>Point the clients to the host's Tailscale IP.</li>
            </ol>

            <h3>Quick start checklist</h3>
            <ol>
                <li>Host PC: install TradeDesk, click <b>Use Local Backend</b>, and log in once.</li>
                <li>Host PC: install Tailscale and sign in.</li>
                <li>Client PCs: install Tailscale and sign in.</li>
                <li>Client PCs: open TradeDesk, choose <b>Use Shared Backend</b>, and paste the host Tailscale URL.</li>
                <li>Test by changing one record on the host and confirming another PC updates.</li>
            </ol>

            <p>If you need internet access outside the office, use the Cloudflare Tunnel option instead of LAN or Tailscale.</p>
            """
        )

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(text)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)


class InitialAdminSetupDialog(QDialog):
    def __init__(self, backend_url: str, parent=None):
        super().__init__(parent)
        self.backend_url = backend_url.rstrip("/")
        self.setWindowTitle("First-Run Admin Setup")
        self.setModal(True)
        self.resize(640, 440)

        intro = QLabel(
            "Create the first super-admin account for this backend now. Share these credentials only with the trusted owner who will manage the system."
        )
        intro.setWordWrap(True)

        form = QFormLayout()
        self.full_name = QLineEdit()
        self.username = QLineEdit()
        self.email = QLineEdit()
        self.password = QLineEdit()
        self.confirm_password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("At least 8 characters with upper, lower, number, and symbol")
        self.confirm_password.setPlaceholderText("Repeat the password")
        self.remember_credentials = QCheckBox("Save these credentials on this PC for the next launch")
        self.remember_credentials.setChecked(False)

        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #E53935;")

        help_button = QPushButton("Setup Help")
        help_button.clicked.connect(self._show_setup_help)
        create_button = QPushButton("Create Admin")
        create_button.clicked.connect(self._create_admin)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        form.addRow("Full Name", self.full_name)
        form.addRow("Username", self.username)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Confirm Password", self.confirm_password)
        form.addRow("", self.remember_credentials)

        buttons = QHBoxLayout()
        buttons.addWidget(help_button)
        buttons.addStretch(1)
        buttons.addWidget(create_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(buttons)

        self.created_credentials: dict[str, str] | None = None

    def _show_setup_help(self) -> None:
        dialog = SetupHelpDialog(self)
        dialog.exec()

    def _create_admin(self) -> None:
        self.error.setText("")

        full_name = self.full_name.text().strip()
        username = self.username.text().strip()
        email = self.email.text().strip() or None
        password = self.password.text()
        confirm = self.confirm_password.text()

        if not full_name or not username or not password:
            self.error.setText("Full name, username, and password are required.")
            return
        if password != confirm:
            self.error.setText("Passwords do not match.")
            return

        payload = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "password": password,
            "role": "super_admin",
        }

        try:
            response = httpx.post(f"{self.backend_url}/api/setup", json=payload, timeout=30.0)
        except Exception as exc:
            self.error.setText(friendly_exception_message(exc, "Create the first admin"))
            return

        if response.status_code not in (200, 201):
            self.error.setText(friendly_http_error(response, "Create the first admin"))
            return

        self.created_credentials = {"username": username, "password": password}

        if self.remember_credentials.isChecked():
            credentials_path = Path.home() / "TradeDesk" / "default-super-admin.json"
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            credentials_path.write_text(
                json.dumps(
                    {
                        "username": username,
                        "full_name": full_name,
                        "email": email,
                        "password": password,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        self.accept()


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


def fetch_setup_status(backend_url: str) -> dict[str, Any] | None:
    try:
        response = httpx.get(f"{backend_url}/api/setup/status", timeout=5.0)
    except Exception:
        return None

    if response.status_code != 200:
        return None

    try:
        body = response.json()
    except Exception:
        return None

    return body if isinstance(body, dict) else None


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
    headless_smoke = _is_truthy(os.environ.get("TRADEDESK_HEADLESS_SMOKE"))

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
            QMessageBox.critical(None, "Backend Unavailable", friendly_exception_message(exc, "Connect to the backend"))
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

    setup_credentials: dict[str, str] | None = None
    if not headless_smoke:
        setup_status = fetch_setup_status(backend_url)
        if setup_status and setup_status.get("needs_initial_admin"):
            setup_dialog = InitialAdminSetupDialog(backend_url)
            if setup_dialog.exec() != QDialog.Accepted:
                return 0
            setup_credentials = setup_dialog.created_credentials

        # Check for updates before creating the main window.
        # This ensures the user gets the update prompt even if the currently
        # installed build has a startup/login bug.
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

    window = MainWindow(backend_url=backend_url)

    if not headless_smoke:
        if not window.ensure_login(initial_credentials=setup_credentials):
            return 0

    window.show()

    exit_code = app.exec()
    if backend_proc is not None:
        stop_backend(backend_proc)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
