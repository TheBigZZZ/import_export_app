from __future__ import annotations

import hashlib
from pathlib import Path

from frontend import update_checker


class _FakeManifestResponse:
    def __init__(self, body: dict[str, object], status_code: int = 200):
        self._body = body
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._body


class _FakeManifestClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str):
        return _FakeManifestResponse(self.body)


def test_update_workflow_downloads_verifies_and_launches(tmp_path, monkeypatch):
    installer_bytes = b"fake installer payload"
    checksum = hashlib.sha256(installer_bytes).hexdigest()
    manifest = {
        "version": "v1.2.3",
        "installer_url": "https://example.com/TradeDeskERP-Setup.exe",
        "installer_sha256": checksum,
    }

    class FakeManifestClient(_FakeManifestClient):
        body = manifest

    launched = {}

    class FakeUpdateDialog:
        def __init__(self, remote_version: str, installer_name: str, parent=None):
            launched["remote_version"] = remote_version
            launched["installer_name"] = installer_name
            launched["parent"] = parent

        def exec(self) -> int:
            return update_checker.QDialog.Accepted

        def run_download(self, installer_url: str, target_path: Path) -> None:
            launched["installer_url"] = installer_url
            target_path.write_bytes(installer_bytes)

        def set_launching(self) -> None:
            launched["launching"] = True

    popen_calls = []

    def fake_popen(args, shell=False):
        popen_calls.append((args, shell))

        class _Proc:
            pass

        return _Proc()

    monkeypatch.setattr(update_checker, "UpdateDialog", FakeUpdateDialog)
    monkeypatch.setattr(update_checker.httpx, "Client", FakeManifestClient)
    monkeypatch.setattr(update_checker.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(update_checker.tempfile, "gettempdir", lambda: str(tmp_path))

    result = update_checker.check_for_update(None, "0.1.0")

    assert result is True
    assert launched["remote_version"] == "1.2.3"
    assert launched["installer_name"] == "TradeDeskERP-Setup.exe"
    assert launched["installer_url"] == manifest["installer_url"]
    assert launched["launching"] is True
    assert popen_calls
    expected_path = tmp_path / "tradedesk-update-1.2.3-TradeDeskERP-Setup.exe"
    assert popen_calls[0][0] == [str(expected_path)]
    assert popen_calls[0][1] is False
    assert expected_path.read_bytes() == installer_bytes


def test_update_workflow_skips_when_current_version_is_newer(monkeypatch):
    manifest = {
        "version": "v1.2.3",
        "installer_url": "https://example.com/TradeDeskERP-Setup.exe",
        "installer_sha256": "a" * 64,
    }

    class FakeManifestClient(_FakeManifestClient):
        body = manifest

    prompt_used = {"value": False}

    class FakeUpdateDialog:
        def __init__(self, remote_version: str, installer_name: str, parent=None):
            prompt_used["value"] = True

        def exec(self) -> int:
            return update_checker.QDialog.Accepted

        def run_download(self, installer_url: str, target_path: Path) -> None:
            raise AssertionError("Should not download when current version is newer")

        def set_launching(self) -> None:
            raise AssertionError("Should not launch when current version is newer")

    monkeypatch.setattr(update_checker, "UpdateDialog", FakeUpdateDialog)
    monkeypatch.setattr(update_checker.httpx, "Client", FakeManifestClient)

    result = update_checker.check_for_update(None, "2.0.0")

    assert result is False
    assert prompt_used["value"] is False