from __future__ import annotations

from typing import Any

import httpx
import keyring

SERVICE_NAME = "TradeDeskERP"
TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def close(self) -> None:
        return None

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        keyring.set_password(SERVICE_NAME, TOKEN_KEY, access_token)
        keyring.set_password(SERVICE_NAME, REFRESH_TOKEN_KEY, refresh_token)

    def clear_tokens(self) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
        except Exception:
            pass
        try:
            keyring.delete_password(SERVICE_NAME, REFRESH_TOKEN_KEY)
        except Exception:
            pass

    def _auth_headers(self) -> dict[str, str]:
        token = keyring.get_password(SERVICE_NAME, TOKEN_KEY)
        return {"Authorization": f"Bearer {token}"} if token else {}

    def auth_headers(self) -> dict[str, str]:
        return self._auth_headers()

    async def post(
        self, path: str, json: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.post(path, json=json, headers=headers)
            return response

    async def get(
        self, path: str, params: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.get(path, params=params, headers=headers)
            return response

    async def put(
        self, path: str, json: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.put(path, json=json, headers=headers)
            return response

    async def delete(self, path: str, auth: bool = True) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            response = await client.delete(path, headers=headers)
            return response

    # Synchronous convenience wrappers for UI worker threads.
    def sync_post(
        self, path: str, json: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            return client.post(path, json=json, headers=headers)

    def sync_get(
        self, path: str, params: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            return client.get(path, params=params, headers=headers)

    def sync_put(
        self, path: str, json: dict[str, Any] | None = None, auth: bool = True
    ) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            return client.put(path, json=json, headers=headers)

    def sync_delete(self, path: str, auth: bool = True) -> httpx.Response:
        headers = self._auth_headers() if auth else {}
        with httpx.Client(base_url=self.base_url, timeout=30.0) as client:
            return client.delete(path, headers=headers)
