from __future__ import annotations

import asyncio
import contextlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class LiveEvent:
    event_type: str
    table_name: str
    action: str
    record_id: int | None = None
    user_id: int | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_payload(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "table_name": self.table_name,
            "action": self.action,
            "record_id": self.record_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
        }


class LiveEventBroker:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[LiveEvent | None]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[LiveEvent | None]:
        queue: asyncio.Queue[LiveEvent | None] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[LiveEvent | None]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)
        with contextlib.suppress(Exception):
            queue.put_nowait(None)

    async def publish(self, event: LiveEvent) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            with contextlib.suppress(Exception):
                queue.put_nowait(event)


broker = LiveEventBroker()


def broadcast_live_event(event: LiveEvent) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(broker.publish(event))
        return

    loop.create_task(broker.publish(event))


def sse_format(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, separators=(',', ':'), ensure_ascii=False)}\n\n"