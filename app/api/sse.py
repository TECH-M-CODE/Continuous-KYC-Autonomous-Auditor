"""SSE streaming router (docs/api_contract.md #7).

Sprint 1 emits a canned demo sequence in lieu of the real IMessageBroker
(Dev 2's app/infrastructure/broker.py), which isn't wired yet.
"""
import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.schemas.events import SSEEvent

router = APIRouter(tags=["events"])

_DEMO_EVENTS: list[SSEEvent] = [
    SSEEvent(
        event="alert.new",
        data={
            "id": "alert-1",
            "entity_id": "entity-1",
            "priority": "CRITICAL",
            "title": "New CRITICAL alert: Acme Import Export Ltd",
        },
    ),
    SSEEvent(
        event="risk.updated",
        data={"entity_id": "entity-1", "score_after": 78.5, "band_after": "HIGH"},
    ),
    SSEEvent(
        event="sar.ready",
        data={"sar_id": "sar-1", "entity_name": "Acme Import Export Ltd", "priority": "CRITICAL"},
    ),
]

_DEMO_EVENT_INTERVAL_SECONDS = 4
_HEARTBEAT_INTERVAL_SECONDS = 15


def _format_sse(event: SSEEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"


async def _event_generator(request: Request) -> AsyncIterator[str]:
    for demo_event in _DEMO_EVENTS:
        if await request.is_disconnected():
            return
        yield _format_sse(demo_event)
        await asyncio.sleep(_DEMO_EVENT_INTERVAL_SECONDS)

    while True:
        if await request.is_disconnected():
            return
        yield ": heartbeat\n\n"
        await asyncio.sleep(_HEARTBEAT_INTERVAL_SECONDS)


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
