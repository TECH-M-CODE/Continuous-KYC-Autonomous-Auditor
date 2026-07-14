"""SSE streaming router — Sprint 3: real broker fan-out replacing canned demo loop.

The SSE handler subscribes to ALL topics so the browser tab receives every
agent-produced event (ALERT_NEW, SAR_READY, ENTITY_UPDATED, SYSTEM_HEALTH,
ALERT_UPDATED, POLICY_RELOADED) over a single connection.

Connection lifecycle:
1. Client connects → handler subscribes to every topic via ``broker.subscription()``.
2. Handler yields one SSE message per broker message.
3. Client disconnects → subscription context-manager cleans up automatically.

The ``HEARTBEAT_INTERVAL_SECONDS`` timeout on ``asyncio.wait_for`` prevents
the generator from stalling forever when no events arrive — it yields a
comment-line heartbeat instead, keeping the HTTP connection alive through
proxies that close idle connections.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.infrastructure.broker import broker

router = APIRouter(tags=["events"])

_HEARTBEAT_INTERVAL_SECONDS = 15


def _format_sse(topic: str, payload) -> str:
    return f"event: {topic}\ndata: {json.dumps(payload, default=str)}\n\n"


async def _event_generator(request: Request) -> AsyncIterator[str]:
    """Async generator: yields SSE frames from the broker until client disconnects."""
    with broker.subscription() as queue:   # subscribe to ALL topics
        while True:
            if await request.is_disconnected():
                return

            try:
                message = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL_SECONDS)
                yield _format_sse(message.topic, message.payload)
            except asyncio.TimeoutError:
                # No events in the last N seconds — emit heartbeat to keep connection alive
                yield ": heartbeat\n\n"
            except asyncio.CancelledError:
                return


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
