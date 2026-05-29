from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import httpx
from PySide6.QtCore import QObject, Signal


class AsyncLiveUpdateMonitor(QObject):
    """Async variant of LiveUpdateMonitor using httpx.AsyncClient.

    Intended for use with a qasync-integrated event loop. It emits the same
    Qt signals as LiveUpdateMonitor so the UI wiring can be reused.
    """

    connected = Signal()
    disconnected = Signal(str)
    event_received = Signal(object)

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api_client = api_client
        self._task: asyncio.Task | None = None
        self._cancel = asyncio.Event()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._cancel = asyncio.Event()
        self._task = asyncio.create_task(self._run())

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._cancel.set()
            self._task.cancel()

    async def _run(self) -> None:
        backoff = 1.0
        while not self._cancel.is_set():
            headers = self.api_client.auth_headers()
            if not headers:
                self.disconnected.emit("Missing access token")
                return

            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream(
                        "GET",
                        f"{self.api_client.base_url}/api/live/events",
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        self.connected.emit()
                        async for raw_line in response.aiter_lines():
                            if self._cancel.is_set():
                                return
                            line = (raw_line or "").strip()
                            # SSE parsing: collect lines until blank line -> event
                            # For simplicity reuse sync builder by delegating
                            # to the sync parser on the main thread if needed.
                            # Here we emit raw lines as minimal events.
                            if line:
                                try:
                                    payload = json.loads(line)
                                except Exception:
                                    payload = {"raw": line}
                                self.event_received.emit(
                                    {"event_name": "message", "payload": payload}
                                )
                backoff = 1.0
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._cancel.is_set():
                    return
                self.disconnected.emit(str(exc))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)


class LiveUpdateMonitor(QObject):
    connected = Signal()
    disconnected = Signal(str)
    event_received = Signal(object)

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api_client = api_client
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        # Attempt a graceful join so resources are cleaned up promptly.
        try:
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
        except Exception:
            pass

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop_event.is_set():
            headers = self.api_client.auth_headers()
            if not headers:
                self.disconnected.emit("Missing access token")
                return

            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    with client.stream(
                        "GET",
                        f"{self.api_client.base_url}/api/live/events",
                        headers=headers,
                    ) as response:
                        response.raise_for_status()
                        self.connected.emit()
                        for event in self._iter_sse_events(response):
                            if self._stop_event.is_set():
                                return
                            self.event_received.emit(event)
                backoff = 1.0
            except Exception as exc:
                if self._stop_event.is_set():
                    return
                self.disconnected.emit(str(exc))
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def _iter_sse_events(self, response: httpx.Response):
        event_name = "message"
        data_lines: list[str] = []

        for raw_line in response.iter_lines():
            if self._stop_event.is_set():
                return
            if raw_line is None:
                continue

            line = raw_line.strip()
            if not line:
                if data_lines:
                    yield self._build_event(event_name, data_lines)
                event_name = "message"
                data_lines = []
                continue

            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip() or "message"
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())

        if data_lines:
            yield self._build_event(event_name, data_lines)

    def _build_event(self, event_name: str, data_lines: list[str]) -> dict[str, Any]:
        payload_text = "\n".join(data_lines)
        try:
            payload = json.loads(payload_text)
        except Exception:
            payload = {"raw": payload_text}
        return {"event_name": event_name, "payload": payload}
