from __future__ import annotations

import json
import os
from pathlib import Path
import base64
from typing import Any

import keyring

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover - optional encryption fallback
    Fernet = None  # type: ignore

from ..config import settings


class SecretStore:
    """Simple secret store that prefers the OS keyring and falls back to
    an encrypted file under the app `data_dir` if keyring isn't available.

    Secrets are stored under the service name 'tradedesk' with the secret key
    used as the username in keyring APIs.
    """

    SERVICE_NAME = "tradedesk"
    _key_file = "secret_store.key"
    _secrets_file = "secrets.enc"

    def __init__(self) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self._key_path = settings.data_dir / self._key_file
        self._secrets_path = settings.data_dir / self._secrets_file
        self._fernet = None
        if Fernet is not None:
            self._ensure_key()

    def _ensure_key(self) -> None:
        if self._fernet is not None:
            return
        if not self._key_path.exists():
            key = Fernet.generate_key()
            self._key_path.write_bytes(key)
            try:
                os.chmod(self._key_path, 0o600)
            except Exception:
                pass
        key = self._key_path.read_bytes()
        self._fernet = Fernet(key)

    def _load_file_store(self) -> dict[str, str]:
        if not self._secrets_path.exists():
            return {}
        data = self._secrets_path.read_bytes()
        if self._fernet is None:
            # Not encrypted — assume plain JSON (legacy)
            try:
                return json.loads(data.decode("utf-8"))
            except Exception:
                return {}
        try:
            plain = self._fernet.decrypt(data)
            return json.loads(plain.decode("utf-8"))
        except Exception:
            return {}

    def _write_file_store(self, d: dict[str, str]) -> None:
        payload = json.dumps(d, ensure_ascii=False).encode("utf-8")
        if self._fernet is not None:
            payload = self._fernet.encrypt(payload)
        self._secrets_path.write_bytes(payload)
        try:
            os.chmod(self._secrets_path, 0o600)
        except Exception:
            pass

    def get(self, key: str) -> str | None:
        try:
            v = keyring.get_password(self.SERVICE_NAME, key)
            if v:
                return v
        except Exception:
            # Keyring failure; fall through to file store
            pass

        store = self._load_file_store()
        return store.get(key)

    def set(self, key: str, value: str) -> None:
        # Try keyring first
        try:
            keyring.set_password(self.SERVICE_NAME, key, value)
            return
        except Exception:
            pass

        store = self._load_file_store()
        store[key] = value
        self._write_file_store(store)

    def delete(self, key: str) -> None:
        try:
            keyring.delete_password(self.SERVICE_NAME, key)
        except Exception:
            pass
        store = self._load_file_store()
        if key in store:
            store.pop(key)
            self._write_file_store(store)


_store = SecretStore()


def get_secret(key: str) -> str | None:
    return _store.get(key)


def set_secret(key: str, value: str) -> None:
    return _store.set(key, value)


def delete_secret(key: str) -> None:
    return _store.delete(key)
