from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..dependencies import get_current_user
from ..live import broker, sse_format
from ..models.user import User

router = APIRouter()


@router.get("/events")
async def live_events(user: User = Depends(get_current_user)) -> StreamingResponse:
    async def event_stream():
        queue = await broker.subscribe()
        try:
            yield sse_format("ready", {"status": "connected", "user_id": user.id})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    break
                yield sse_format(event.event_type, event.to_payload())
        finally:
            await broker.unsubscribe(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )