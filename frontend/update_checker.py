from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple

import httpx
from PySide6.QtWidgets import QMessageBox


_DOWNLOAD_TIMEOUT = 120.0
_DOWNLOAD_CHUNK_SIZE = 1024 * 1024
_MAX_DOWNLOAD_RETRIES = 3


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


def _download_file(url: str, target_path: Path) -> None:
    tmp_path = target_path.with_suffix(target_path.suffix + ".part")
    with httpx.Client(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            with tmp_path.open("wb") as fh:
                for chunk in resp.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        fh.write(chunk)
    tmp_path.replace(target_path)


def check_for_update(parent, current_version: str) -> None:
    """Check a remote manifest (configured via TRADEDESK_UPDATE_MANIFEST_URL).
    If an update is available, prompt the user to download and run the installer.
    This is intentionally lightweight and uses a simple manifest format:

    {
      "version": "1.2.3",
      "installer_url": "https://.../TradeDeskInstaller.exe",
            "installer_sha256": "..."   (required in production)
    }
    """
    manifest_url = os.environ.get("TRADEDESK_UPDATE_MANIFEST_URL")
    if not manifest_url:
        return

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(manifest_url)
            if resp.status_code != 200:
                return
            body = resp.json()
    except Exception:
        return

    remote_ver = body.get("version")
    installer = body.get("installer_url")
    checksum = _normalize_sha256(body.get("installer_sha256") or body.get("checksum"))
    if not remote_ver or not installer:
        return

    if not installer.lower().startswith("https://"):
        # For safety, only allow HTTPS update URLs.
        return

    try:
        if _parse_version(remote_ver) <= _parse_version(current_version):
            return
    except Exception:
        return

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Question)
    msg.setWindowTitle("Update Available")
    msg.setText(f"A new version ({remote_ver}) is available. Download and install now?")
    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    res = msg.exec()
    if res != QMessageBox.Yes:
        return

    # Download installer to temp and run.
    try:
        tmpdir = Path(tempfile.gettempdir())
        out = tmpdir / f"tradedesk-update-{remote_ver}-{Path(installer).name}"

        last_error: Exception | None = None
        for _ in range(_MAX_DOWNLOAD_RETRIES):
            try:
                _download_file(installer, out)
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
        if os.name == "nt":
            subprocess.Popen([str(out)], shell=False)
        else:
            subprocess.Popen(["chmod", "+x", str(out)])
            subprocess.Popen([str(out)])
    except Exception:
        err = QMessageBox()
        err.setIcon(QMessageBox.Warning)
        err.setWindowTitle("Update Failed")
        err.setText("Failed to download, verify, or launch the installer.")
        err.exec()
