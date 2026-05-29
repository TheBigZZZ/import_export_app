from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from PySide6.QtCore import QEventLoop, QThreadPool
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFormLayout,
                               QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTextBrowser,
                               QVBoxLayout)

from frontend.backend_manager import BackendManager
from frontend.workers import Worker

try:
    from tradedesk.backend.config import settings as backend_settings

    from frontend.app_version import get_app_version
    from frontend.connection_settings import (ConnectionSettings,
                                              clear_connection_settings,
                                              load_connection_settings,
                                              save_connection_settings)
    from frontend.error_messages import friendly_exception_message, friendly_http_error
    from frontend.mainwindow import MainWindow
except ImportError:
    from tradedesk.backend.config import settings as backend_settings
    from frontend.app_version import get_app_version
    from frontend.connection_settings import (ConnectionSettings,
                                              clear_connection_settings,
                                              load_connection_settings,
                                              save_connection_settings)
    from frontend.error_messages import (friendly_exception_message,
                                         friendly_http_error)
    from frontend.mainwindow import MainWindow

BACKEND_PORT = 8742
BACKEND_STARTUP_TIMEOUT_SECONDS = 90
BACKEND_STARTUP_POLL_INTERVAL_SECONDS = 0.5

# PID file for the spawned local backend process
PID_FILE = Path.home() / "TradeDesk" / "backend.pid"
_BACKEND_JOB_HANDLE: int | None = None


def _close_backend_job_handle() -> None:
    global _BACKEND_JOB_HANDLE

    if os.name != "nt" or not _BACKEND_JOB_HANDLE:
        return

    try:
        ctypes.windll.kernel32.CloseHandle(_BACKEND_JOB_HANDLE)
    except Exception:
        pass
    finally:
        _BACKEND_JOB_HANDLE = None


def _attach_backend_job_object(proc: Any) -> None:
    if os.name != "nt":
        return

    global _BACKEND_JOB_HANDLE
    _close_backend_job_handle()

    try:
        kernel32 = ctypes.windll.kernel32

        job_handle = kernel32.CreateJobObjectW(None, None)
        if not job_handle:
            return

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", ctypes.wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.wintypes.DWORD),
                ("SchedulingClass", ctypes.wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        limit_info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limit_info.BasicLimitInformation.LimitFlags = (
            0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if not kernel32.SetInformationJobObject(
            job_handle, 9, ctypes.byref(limit_info), ctypes.sizeof(limit_info)
        ):
            kernel32.CloseHandle(job_handle)
            return

        process_handle = getattr(proc, "_handle", None)
        close_process_handle = False
        if not process_handle:
            process_handle = kernel32.OpenProcess(0x001F0FFF, False, int(proc.pid))
            close_process_handle = bool(process_handle)

        if not process_handle:
            kernel32.CloseHandle(job_handle)
            return

        if not kernel32.AssignProcessToJobObject(job_handle, process_handle):
            if close_process_handle:
                kernel32.CloseHandle(process_handle)
            kernel32.CloseHandle(job_handle)
            return

        if close_process_handle:
            kernel32.CloseHandle(process_handle)

        _BACKEND_JOB_HANDLE = job_handle
    except Exception:
        try:
            if _BACKEND_JOB_HANDLE:
                ctypes.windll.kernel32.CloseHandle(_BACKEND_JOB_HANDLE)
        except Exception:
            pass
        _BACKEND_JOB_HANDLE = None


def _is_truthy(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_backend_target() -> tuple[str, bool, bool]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend-url")
    parser.add_argument("--configure-connection", action="store_true")
    args, _ = parser.parse_known_args(sys.argv[1:])

    backend_url = (
        args.backend_url or os.environ.get("TRADEDESK_BACKEND_URL") or ""
    ).strip()
    if backend_url:
        if "://" not in backend_url:
            backend_url = f"http://{backend_url}"
        return backend_url.rstrip("/"), False, False

    # Smoke tests must always start a local backend so the packaged EXE is
    # validated end-to-end instead of reusing any persisted connection URL.
    if _is_truthy(os.environ.get("TRADEDESK_HEADLESS_SMOKE")):
        return f"http://127.0.0.1:{BACKEND_PORT}", True, False

    stored = load_connection_settings()
    if (
        stored
        and not args.configure_connection
        and not os.environ.get("TRADEDESK_CONFIGURE_CONNECTION")
    ):
        backend_url = stored.backend_url.strip()
        if backend_url:
            if "://" not in backend_url:
                backend_url = f"http://{backend_url}"
            is_local = backend_url.startswith(
                "http://127.0.0.1"
            ) or backend_url.startswith("http://localhost")
            return backend_url.rstrip("/"), is_local, False

    # If a local database already exists, assume this is a relaunch of a
    # previously configured local install and skip the connection chooser.
    # This avoids re-showing setup after a normal close or crash when the
    # user intentionally chose not to remember the host URL.
    try:
        if (
            backend_settings.db_path.exists()
            and not args.configure_connection
            and not os.environ.get("TRADEDESK_CONFIGURE_CONNECTION")
        ):
            return f"http://127.0.0.1:{BACKEND_PORT}", True, False
    except Exception:
        pass

    return f"http://127.0.0.1:{BACKEND_PORT}", True, True


class ConnectionSetupDialog(QDialog):
    def __init__(self, initial_backend_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Connection Setup")
        self.setModal(True)

        intro = QLabel(
            "Choose how this desktop connects to TradeDesk. Local mode starts a backend "
            "on this PC. Shared mode points all PCs to one backend host on your network."
        )
        intro.setWordWrap(True)

        guidance = QLabel(
            "Recommended for nontechnical users: use Tailscale so everyone can "
            "connect to one host PC without firewall changes or port forwarding."
        )
        guidance.setWordWrap(True)
        guidance.setObjectName("mutedLabel")

        self.backend_url = QLineEdit(initial_backend_url)
        self.backend_url.setPlaceholderText(
            "http://127.0.0.1:8742 or http://192.168.1.50:8742"
        )
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
            QMessageBox.warning(
                self,
                "Connection Setup",
                "Enter a backend URL first, or choose Use Local Backend.",
            )
            return
        self.accept()

    def selected_settings(self) -> ConnectionSettings:
        backend_url = self.backend_url.text().strip()
        if "//" not in backend_url:
            backend_url = f"http://{backend_url}"
        return ConnectionSettings(
            backend_url=backend_url.rstrip("/"), remember=self.remember.isChecked()
        )


class SetupHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Setup Guide")
        self.setModal(True)
        self.resize(780, 640)

        text = QTextBrowser(self)
        text.setOpenExternalLinks(True)
        text.setHtml("""
            <h2>Recommended setup for nontechnical users</h2>
            <p>
                <b>Best simple choice:</b> use
                <a href="https://tailscale.com/download">Tailscale</a> on one
                host PC and on every client PC.
                It lets the app connect to one shared backend without port
                forwarding, router changes, or static IP setup.
            </p>
            <p>
                <b>If you need internet access outside the office:</b> use
                (
                    '<a href="https://developers.cloudflare.com/cloudflare-one/'
                    'connections/connect-networks/get-started/create-remote-tunnel/">'
                    "Cloudflare Tunnel"
                    "</a>"
                )
                or another public HTTPS tunnel on the host machine.
            </p>

            <h3>Option A - Local setup on one PC</h3>
            <ol>
                <li>
                    Install TradeDesk on the PC you want to use as the main
                    machine.
                </li>
                <li>Open the app and click <b>Use Local Backend</b>.</li>
                <li>
                    Leave the URL as <code>http://127.0.0.1:8742</code>.
                </li>
                <li>Log in with the admin account.</li>
                <li>
                    Keep that app open; it will start and use the local
                    backend automatically.
                </li>
            </ol>

            <h3>Option B - Shared setup using Tailscale</h3>
            <ol>
                <li>Pick one always-on PC to act as the host.</li>
                <li>Install TradeDesk on the host PC and open it once.</li>
                <li>On the host PC, click <b>Use Local Backend</b>.</li>
                <li>
                    Install Tailscale on the host PC from
                    <a href="https://tailscale.com/download">tailscale.com/download</a>.
                </li>
                <li>Sign in to Tailscale on the host PC.</li>
                <li>
                    Install Tailscale on every client PC and sign in with the
                    same Tailscale account or invite those users to your
                    tailnet.
                </li>
                <li>
                    In the Tailscale admin page, find the host PC's Tailscale
                    IP address, usually starting with <code>100.</code>.
                </li>
                <li>
                    On each client PC, open TradeDesk and choose
                    <b>Use Shared Backend</b>.
                </li>
                <li>
                    Enter the Tailscale address exactly, for example
                    <code>http://100.101.102.103:8742</code>.
                </li>
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
                <li>
                    Host PC: install TradeDesk, click
                    <b>Use Local Backend</b>, and log in once.
                </li>
                <li>Host PC: install Tailscale and sign in.</li>
                <li>Client PCs: install Tailscale and sign in.</li>
                <li>
                    Client PCs: open TradeDesk, choose
                    <b>Use Shared Backend</b>, and paste the host Tailscale URL.
                </li>
                <li>
                    Test by changing one record on the host and confirming
                    another PC updates.
                </li>
            </ol>

            <p>
                If you need internet access outside the office, use the
                Cloudflare Tunnel option instead of LAN or Tailscale.
            </p>
            """)

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
            (
                "Create the first super-admin account for this backend now. Share "
                "these credentials only with the trusted owner who will manage "
                "the system."
            )
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
        self.password.setPlaceholderText(
            "At least 8 characters with upper, lower, number, and symbol"
        )
        self.confirm_password.setPlaceholderText("Repeat the password")
        self.remember_credentials = QCheckBox(
            "Save these credentials on this PC for the next launch"
        )
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

        # Run setup request in a worker so the dialog doesn't freeze.
        result_holder = {}

        def _do_setup():
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self.backend_url}/api/setup", json=payload)
                resp.raise_for_status()
                return resp

        loop = QEventLoop()

        def _on_result(resp):
            result_holder["resp"] = resp
            loop.quit()

        def _on_error(exc):
            result_holder["error"] = exc
            loop.quit()

        worker = Worker(_do_setup)
        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        QThreadPool.globalInstance().start(worker)
        loop.exec()

        if "error" in result_holder:
            self.error.setText(
                friendly_exception_message(
                    result_holder["error"], "Create the first admin"
                )
            )
            return

        response = result_holder.get("resp")
        if response is None or response.status_code not in (200, 201):
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

    backend_cmd = [sys.executable, "--backend-cli", "--serve"]
    log_path = Path(tempfile.gettempdir()) / "tradedesk-backend.log"
    log_file = open(log_path, "a", encoding="utf-8")
    env = dict(os.environ)
    env["TRADEDESK_BACKEND_CHILD"] = "1"
    try:
        # Best-effort stop of any previous backend recorded in PID file
        try:
            if PID_FILE.exists():
                try:
                    raw = PID_FILE.read_text(encoding="utf-8").strip()
                    old_pid = int(raw) if raw else 0
                except Exception:
                    old_pid = 0

                if old_pid:
                    # Check whether the PID actually refers to a running process.
                    if os.name == "nt":
                        # Use tasklist to confirm the PID exists on Windows.
                        proc = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {old_pid}", "/FO", "CSV"],
                            capture_output=True,
                            text=True,
                        )
                        if proc.returncode != 0 or str(old_pid) not in proc.stdout:
                            try:
                                PID_FILE.unlink()
                            except Exception:
                                pass
                        else:
                            # Best-effort terminate the previous backend process
                            subprocess.run(
                                ["taskkill", "/PID", str(old_pid), "/F", "/T"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                    else:
                        try:
                            os.kill(old_pid, 0)
                        except Exception:
                            try:
                                PID_FILE.unlink()
                            except Exception:
                                pass
                        else:
                            try:
                                os.killpg(old_pid, signal.SIGTERM)
                            except Exception:
                                try:
                                    os.kill(old_pid, signal.SIGTERM)
                                except Exception:
                                    pass
                else:
                    try:
                        PID_FILE.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            creationflags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)

        proc = subprocess.Popen(
            backend_cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=str(Path(sys.executable).parent),
            creationflags=creationflags,
            env=env,
        )

        try:
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass

        _attach_backend_job_object(proc)

        for _ in range(
            int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)
        ):
            try:
                httpx.get(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1.0)
                return proc
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"Backend exited early with code {proc.returncode}; see {log_path}"
                    )
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

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        creationflags |= getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)

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
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    except Exception:
        pass

    _attach_backend_job_object(proc)

    for _ in range(
        int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)
    ):
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
    for _ in range(
        int(BACKEND_STARTUP_TIMEOUT_SECONDS / BACKEND_STARTUP_POLL_INTERVAL_SECONDS)
    ):
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
    try:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/F", "/T"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

        if hasattr(proc, "wait"):
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        else:
            try:
                proc.join(timeout=3)
            except Exception:
                pass
    finally:
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass
        _close_backend_job_handle()


def load_styles(app: QApplication, project_root: Path) -> None:
    qss_path = project_root / "frontend" / "assets" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main() -> int:
    if getattr(sys, "frozen", False):
        project_root = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        project_root = Path(__file__).resolve().parents[1]

    import tempfile as _tempfile

    _debug_log = Path(_tempfile.gettempdir()) / "tradedesk-frontend-debug.log"

    def _dbg(msg: str) -> None:
        try:
            _debug_log.parent.mkdir(parents=True, exist_ok=True)
            with _debug_log.open("a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now().isoformat()} - {msg}\n")
        except Exception:
            pass

    _dbg("starting main")

    headless_smoke = _is_truthy(os.environ.get("TRADEDESK_HEADLESS_SMOKE"))

    # In CI smoke mode, run the backend directly inside the packaged EXE.
    # This avoids the GUI/bootstrap child-process chain and gives the smoke
    # test a deterministic /health endpoint to probe.
    if headless_smoke:
        from tradedesk.backend.cli import main as backend_cli_main

        _dbg("headless smoke -> serving backend directly")
        return backend_cli_main(["--serve"])

    app = QApplication(sys.argv)

    if _is_truthy(os.environ.get("TRADEDESK_USE_QTASYNCIO")):
        try:
            from PySide6.QtAsyncio import QAsyncioEventLoopPolicy

            asyncio.set_event_loop_policy(QAsyncioEventLoopPolicy())
            _dbg("qtasyncio policy enabled")
        except Exception as exc:
            _dbg(f"qtasyncio policy unavailable: {exc}")

    # Load styles before showing any dialogs so dialogs honor app stylesheet.
    load_styles(app, project_root)
    _dbg("styles loaded")

    # Check for updates before showing the connection/setup dialog or starting any backend.
    # If an installer is launched, exit so the new build can take over cleanly.
    if not headless_smoke:
        try:
            # Run update check in a background worker so startup isn't blocked by network latency.
            from frontend.update_checker import check_for_update
            from frontend.workers import Worker

            update_result = {}

            def _do_update_check():
                try:
                    return check_for_update(None, get_app_version())
                except Exception:
                    return False

            def _on_update(res):
                update_result["accepted"] = bool(res)

            def _on_update_err(exc):
                update_result["error"] = exc

            worker = Worker(_do_update_check)
            worker.signals.result.connect(_on_update)
            worker.signals.error.connect(_on_update_err)
            QThreadPool.globalInstance().start(worker)

            # Give the update check a short grace period to decide; if it returns True
            # we will exit early. Otherwise continue startup and let the worker finish.
            timeout = 3.0
            start_t = time.time()
            while time.time() - start_t < timeout:
                if "accepted" in update_result and update_result["accepted"]:
                    _dbg("update accepted -> exiting")
                    return 0
                if "error" in update_result:
                    _dbg("update check reported error")
                    break
                time.sleep(0.05)

        except Exception:
            _dbg("update check failed or raised")

    _dbg("update check completed")

    backend_url, should_start_local, should_prompt = _resolve_backend_target()
    _dbg(
        f"resolved backend target: {backend_url}, should_start_local={should_start_local}, "
        f"should_prompt={should_prompt}"
    )

    # Show the connection/setup dialog only after the update gate has passed.
    if (
        should_prompt
        or os.environ.get("TRADEDESK_CONFIGURE_CONNECTION")
        or "--configure-connection" in sys.argv[1:]
    ):
        dialog = ConnectionSetupDialog(backend_url)
        if dialog.exec() == QDialog.Accepted:
            chosen = dialog.selected_settings()
            backend_url = chosen.backend_url
            should_start_local = backend_url.startswith(
                "http://127.0.0.1"
            ) or backend_url.startswith("http://localhost")
            if chosen.remember:
                save_connection_settings(chosen)
            else:
                clear_connection_settings()
        else:
            return 0

    backend_proc = None
    if should_start_local:
        try:
            backend_proc = BackendManager().start(project_root)
        except Exception:
            backend_proc = None
    _dbg(f"backend_proc set: {bool(backend_proc)}")

    def restart_local_backend() -> Any:
        nonlocal backend_proc
        # If a backend is already running, return it
        try:
            if backend_proc is not None:
                return backend_proc
        except Exception:
            pass
        try:
            proc = BackendManager().restart(project_root)
            backend_proc = proc
            return proc
        except Exception:
            return None

    def _shutdown_backend() -> None:
        try:
            # Ask BackendManager to stop any managed backend. If we started none, this is a no-op.
            try:
                BackendManager().stop()
            except Exception:
                # Fallback: if a proc object exists, try best-effort stop
                if backend_proc is not None:
                    stop_backend(backend_proc)
        except Exception:
            pass

    def _unhandled_exception_hook(exc_type, exc, tb) -> None:
        _shutdown_backend()
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _unhandled_exception_hook

    # Ensure backend is stopped when the application is quitting.
    try:
        app.aboutToQuit.connect(_shutdown_backend)
    except Exception:
        # best-effort; continue if connect fails
        pass

    try:
        app.setQuitOnLastWindowClosed(True)
        app.lastWindowClosed.connect(app.quit)
    except Exception:
        pass

    if not should_start_local:
        try:
            # Run wait_for_backend in a background worker so the UI remains responsive.
            wait_result: dict[str, object] = {}

            def _do_wait():
                wait_for_backend(backend_url)
                return True

            def _on_wait(res):
                wait_result["ok"] = True

            def _on_wait_err(exc):
                wait_result["error"] = exc

            worker = Worker(_do_wait)
            worker.signals.result.connect(_on_wait)
            worker.signals.error.connect(_on_wait_err)
            QThreadPool.globalInstance().start(worker)

            loop = QEventLoop()

            def _on_finished():
                loop.quit()

            worker.signals.finished.connect(_on_finished)
            loop.exec()

            if "error" in wait_result:
                QMessageBox.critical(
                    None,
                    "Backend Unavailable",
                    friendly_exception_message(
                        wait_result["error"], "Connect to the backend"
                    ),
                )
                return 1
        except Exception as exc:
            QMessageBox.critical(
                None,
                "Backend Unavailable",
                friendly_exception_message(exc, "Connect to the backend"),
            )
            return 1

    # If a diagnostic traceback file exists from a previous run, offer the
    # user the option to upload it to a secure endpoint for debugging.
    try:
        import tempfile

        tmp = Path(tempfile.gettempdir()) / "tradedesk-backend-error.txt"
        upload_url = os.environ.get(
            "TRADEDESK_DIAGNOSTICS_UPLOAD_URL"
        ) or os.environ.get("TRADEDESK_DIAGNOSTICS_UPLOAD_URL_LOCAL")
        if tmp.exists() and upload_url:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setWindowTitle("Send Diagnostic Report")
            msg.setText(
                "The application detected an error report from a previous run.\n"
                "Would you like to upload it to the support server to help "
                "diagnose the problem?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            res = msg.exec()
            if res == QMessageBox.Yes:
                email, ok = QInputDialog.getText(
                    None, "Contact Email (optional)", "Email:"
                )
                description, _ = QInputDialog.getText(
                    None, "Description (optional)", "Describe what you were doing:"
                )
                try:
                    import hmac
                    import json

                    import httpx

                    # prepared file content is used directly when posting
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
                                resp = client.post(
                                    upload_url.replace("/upload", "/register"), data={}
                                )
                            if resp.status_code == 200:
                                body = resp.json()
                                install_id = body.get("install_id")
                                install_secret = body.get("install_secret")
                                if install_id and install_secret:
                                    install_store.parent.mkdir(
                                        parents=True, exist_ok=True
                                    )
                                    install_store.write_text(
                                        json.dumps(
                                            {
                                                "install_id": install_id,
                                                "install_secret": install_secret,
                                            }
                                        )
                                    )
                        except Exception:
                            # registration failed; continue without signing
                            install_id = None
                            install_secret = None

                    # If we have an install secret, compute signature and include headers (timestamp + nonce)
                    headers = {}
                    body_bytes = tmp.read_bytes()
                    if install_id and install_secret:
                        timestamp = datetime.now(timezone.utc).strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        )
                        nonce = uuid.uuid4().hex
                        payload = f"{timestamp}\n{nonce}\n".encode("utf-8") + body_bytes
                        mac = hmac.new(
                            install_secret.encode("utf-8"), payload, "sha256"
                        ).hexdigest()
                        headers["X-Install-Id"] = install_id
                        headers["X-Signature"] = mac
                        headers["X-Signature-Timestamp"] = timestamp
                        headers["X-Signature-Nonce"] = nonce

                    # Use httpx to post with headers
                    with httpx.Client(timeout=15.0) as client:
                        resp = client.post(
                            upload_url,
                            files={"file": (tmp.name, body_bytes, "text/plain")},
                            data=data,
                            headers=headers,
                        )

                    if resp.status_code == 200:
                        QMessageBox.information(
                            None,
                            "Uploaded",
                            (
                                "Diagnostic uploaded. Ticket: "
                                f"{resp.json().get('ticket')}"
                            ),
                        )
                        try:
                            tmp.unlink()
                        except Exception:
                            pass
                    else:
                        QMessageBox.warning(
                            None,
                            "Upload Failed",
                            f"Server returned: {resp.status_code}",
                        )
                except Exception as exc:
                    QMessageBox.warning(None, "Upload Failed", str(exc))
    except Exception:
        # keep UI responsive if diagnostics flow fails
        pass

    setup_credentials: dict[str, str] | None = None
    if not headless_smoke:
        # Fetch setup status in a worker to avoid blocking the UI thread.
        try:
            setup_holder: dict[str, object] = {}

            def _do_fetch():
                return fetch_setup_status(backend_url)

            def _on_fetch(res):
                setup_holder["body"] = res

            def _on_fetch_err(exc):
                setup_holder["error"] = exc

            worker = Worker(_do_fetch)
            worker.signals.result.connect(_on_fetch)
            worker.signals.error.connect(_on_fetch_err)
            QThreadPool.globalInstance().start(worker)

            loop = QEventLoop()

            def _on_fetch_finished():
                loop.quit()

            worker.signals.finished.connect(_on_fetch_finished)
            loop.exec()

            setup_status = setup_holder.get("body") if "body" in setup_holder else None
        except Exception:
            setup_status = None

        if setup_status and setup_status.get("needs_initial_admin"):
            setup_dialog = InitialAdminSetupDialog(backend_url)
            if setup_dialog.exec() != QDialog.Accepted:
                return 0
            setup_credentials = setup_dialog.created_credentials

    window = MainWindow(
        backend_url=backend_url,
        on_close=_shutdown_backend,
        restart_local_backend=restart_local_backend,
    )

    if not headless_smoke:
        if not window.ensure_login(initial_credentials=setup_credentials):
            return 0

    window.show()

    # Also handle OS signals to ensure clean shutdown when possible.
    try:

        def _signal_handler(signum, frame):
            _shutdown_backend()
            try:
                QApplication.quit()
            except Exception:
                pass

        signal.signal(signal.SIGINT, _signal_handler)
        try:
            signal.signal(signal.SIGTERM, _signal_handler)
        except Exception:
            # Some platforms may not support SIGTERM
            pass
    except Exception:
        pass

    exit_code = app.exec()
    _shutdown_backend()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
