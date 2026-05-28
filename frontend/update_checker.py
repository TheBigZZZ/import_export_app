from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

import httpx

try:  # pragma: no cover - exercised indirectly in GUI environments
    from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout
except Exception:  # pragma: no cover - used in headless CI where Qt system libs are unavailable
    class _QtBase:
        def __init__(self, *args, **kwargs):
            pass

    class QApplication(_QtBase):
        @staticmethod
        def processEvents() -> None:
            return None

    class QDialog(_QtBase):
        Accepted = 1
        Rejected = 0

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._result = self.Rejected

        def setWindowTitle(self, *args, **kwargs):
            return None

        def setModal(self, *args, **kwargs):
            return None

        def setMinimumWidth(self, *args, **kwargs):
            return None

        def exec(self) -> int:
            return self._result

        def accept(self) -> None:
            self._result = self.Accepted

        def reject(self) -> None:
            self._result = self.Rejected

    class QHBoxLayout(_QtBase):
        def addStretch(self, *args, **kwargs):
            return None

        def addWidget(self, *args, **kwargs):
            return None

    class QVBoxLayout(QHBoxLayout):
        def __init__(self, *args, **kwargs):
            pass

        def addLayout(self, *args, **kwargs):
            return None

    class QLabel(_QtBase):
        def __init__(self, *args, **kwargs):
            self._text = args[0] if args else ""

        def setWordWrap(self, *args, **kwargs):
            return None

        def setStyleSheet(self, *args, **kwargs):
            return None

        def setObjectName(self, *args, **kwargs):
            return None

        def setText(self, text: str) -> None:
            self._text = text

    class QMessageBox(_QtBase):
        Warning = 1
        Question = 2
        Yes = 1
        No = 0

        def setIcon(self, *args, **kwargs):
            return None

        def setWindowTitle(self, *args, **kwargs):
            return None

        def setText(self, *args, **kwargs):
            return None

        def setStandardButtons(self, *args, **kwargs):
            return None

        def exec(self) -> int:
            return self.Yes

    class QProgressBar(_QtBase):
        def setRange(self, *args, **kwargs):
            return None

        def setValue(self, *args, **kwargs):
            return None

        def setTextVisible(self, *args, **kwargs):
            return None

        def hide(self):
            return None

        def show(self):
            return None

    class QPushButton(_QtBase):
        class _Signal:
            def connect(self, *args, **kwargs):
                return None

        def __init__(self, *args, **kwargs):
            self.clicked = self._Signal()



_DOWNLOAD_TIMEOUT = 120.0
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_MAX_DOWNLOAD_RETRIES = 3


def _clean_version_label(ver: str | None) -> str:
    if not ver:
        return ""
    return ver.strip().lstrip("vV").strip()


def _parse_version(ver: str) -> Tuple[int, ...]:
    parts = []
    for p in ver.split("."):
        try:
            parts.append(int(p))
        except Exception:
            parts.append(0)
    return tuple(parts)


def _normalize_sha256(value: str | None) -> str | None:
    if not value:
        return None
    txt = value.strip().lower()
    if txt.startswith("sha256:"):
        txt = txt.split(":", 1)[1].strip()
    if len(txt) != 64:
        return None
    try:
        int(txt, 16)
    except ValueError:
        return None
    return txt


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(max(value, 0))
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{int(size)} B"


class UpdateDialog(QDialog):
    def __init__(self, remote_version: str, installer_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TradeDesk Update Available")
        self.setModal(True)
        self.setMinimumWidth(520)

        self.title_label = QLabel(f"A new version ({remote_version}) is ready to install.")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 600;")

        self.body_label = QLabel(
            f"TradeDesk will download {installer_name} from GitHub, verify it, then launch the installer and close the current app."
        )
        self.body_label.setWordWrap(True)

        self.status_label = QLabel("Click Update Now to begin.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("mutedLabel")

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.hide()

        self.update_button = QPushButton("Update Now")
        self.update_button.clicked.connect(self.accept)
        self.later_button = QPushButton("Later")
        self.later_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.update_button)
        buttons.addWidget(self.later_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addLayout(buttons)

    def _set_busy(self, text: str) -> None:
        self.progress.setRange(0, 0)
        self.progress.show()
        self.status_label.setText(text)
        QApplication.processEvents()

    def _set_progress(self, percent: int, text: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(max(0, min(percent, 100)))
        self.status_label.setText(text)
        QApplication.processEvents()

    def _download_with_progress(self, url: str, target_path: Path) -> None:
        tmp_path = target_path.with_suffix(target_path.suffix + ".part")
        with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                downloaded = 0
                self._set_busy("Downloading update package...")
                with tmp_path.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = int((downloaded / total) * 100)
                            self._set_progress(percent, f"Downloading update package... {_format_bytes(downloaded)} / {_format_bytes(total)}")
                        else:
                            self._set_busy(f"Downloading update package... {_format_bytes(downloaded)}")
        tmp_path.replace(target_path)

    def run_download(self, installer_url: str, target_path: Path) -> None:
        self.update_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self._download_with_progress(installer_url, target_path)
        self._set_progress(100, "Verifying download...")

    def set_launching(self) -> None:
        self._set_progress(100, "Launching installer and closing TradeDesk...")


def check_for_update(parent, current_version: str) -> bool:
    """Check a remote manifest (configured via TRADEDESK_UPDATE_MANIFEST_URL).
    If an update is available, prompt the user to download and run the installer.
    This is intentionally lightweight and uses a simple manifest format:

    {
      "version": "1.2.3",
      "installer_url": "https://.../TradeDeskInstaller.exe",
            "installer_sha256": "..."   (required in production)
    }
    """
    # Developer/testing shortcut: simulate the user accepting an update and
    # launching the installer by setting TRADEDESK_SIMULATE_ACCEPT_UPDATE=1.
    if os.environ.get("TRADEDESK_SIMULATE_ACCEPT_UPDATE", "").strip().lower() in {"1", "true", "yes"}:
        return True

    manifest_url = os.environ.get("TRADEDESK_UPDATE_MANIFEST_URL")
    # Default to the repo's latest release manifest if not configured.
    if not manifest_url:
        # Replace owner/repo with this project's repository so users don't need to set an env var.
        manifest_url = "https://github.com/TheBigZZZ/import_export_app/releases/latest/download/updates.json"

    try:
        # follow redirects: GitHub release asset URLs may redirect
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(manifest_url)
            if resp.status_code != 200:
                return False
            body = resp.json()
    except Exception:
        return False

    remote_ver = _clean_version_label(body.get("version"))
    installer = body.get("installer_url")
    checksum = _normalize_sha256(body.get("installer_sha256") or body.get("checksum"))
    if not remote_ver or not installer:
        return False

    if not installer.lower().startswith("https://"):
        # For safety, only allow HTTPS update URLs.
        return False

    try:
        if _parse_version(remote_ver) <= _parse_version(_clean_version_label(current_version)):
            return False
    except Exception:
        return False

    installer_name = Path(str(installer)).name

    prompt = UpdateDialog(remote_ver, installer_name, parent)
    if prompt.exec() != QDialog.Accepted:
        return False

    # Download installer to temp and run.
    try:
        tmpdir = Path(tempfile.gettempdir())
        out = tmpdir / f"tradedesk-update-{remote_ver}-{installer_name}"

        last_error: Exception | None = None
        for _ in range(_MAX_DOWNLOAD_RETRIES):
            try:
                prompt.run_download(installer, out)
                last_error = None
                break
            except Exception as exc:  # pragma: no cover - network/runtime behavior
                last_error = exc
        if last_error is not None:
            raise last_error

        # Enforce checksum validation unless explicitly bypassed for local testing.
        allow_unsigned = os.environ.get("TRADEDESK_ALLOW_UNSIGNED_UPDATE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
        if checksum:
            actual = _sha256_file(out)
            if actual.lower() != checksum.lower():
                raise RuntimeError("Downloaded installer checksum mismatch.")
        elif not allow_unsigned:
            raise RuntimeError("Update manifest missing installer checksum.")

        # Attempt to launch installer (non-blocking)
        prompt.set_launching()
        if os.name == "nt":
            subprocess.Popen([str(out)], shell=False)
        else:
            subprocess.Popen(["chmod", "+x", str(out)])
            subprocess.Popen([str(out)])
        return True
    except Exception:
        err = QMessageBox()
        err.setIcon(QMessageBox.Warning)
        err.setWindowTitle("Update Failed")
        err.setText("Failed to download, verify, or launch the installer.")
        err.exec()
        return False
