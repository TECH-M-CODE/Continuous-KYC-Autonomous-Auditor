"""FeedAdapter ABC, shared adapter helpers, and the ingestion run loops.

Naming note: adapters produce ``IngestedEvent`` here, not ``RawEvent``. The
Sprint 2 plan's pseudocode uses ``RawEvent``, but that name is already
Dev 1's SQLAlchemy model (``app.models.events.RawEvent`` / table
``events_raw``), which has no ``event_type`` or ``payload`` column -- only
``content`` (Text), ``title``, ``source_url``, ``content_hash``, ``status``.
``to_orm_event()`` below JSON-encodes ``{event_type, source, text, payload,
entity_hint}`` into ``content``, the same Text-as-JSON convention already
used by ``SanctionsCache.aliases`` and ``AuditLog.payload`` elsewhere in
this codebase.

Two loops, per the plan:
  * Loop A: one scheduled job per adapter (``adapter.schedule_seconds``),
    running ``run_adapter_once`` -- fetch, dedupe, persist, all inside one
    UnitOfWork so a failure partway through commits nothing.
  * Loop B: a 5s poll of unprocessed events, handed to a pluggable
    ``handler`` -- Dev 3's ``traced_pipeline`` once it exists this sprint.
    Until then, pass ``handler=None``; unprocessed events are logged and
    left untouched rather than guessed at.

Neither loop is wired into app/main.py's lifespan by this file -- main.py
is shared across every dev now, so that wiring is a separate, explicit step.
"""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.infrastructure.broker import SYSTEM_HEALTH, AsyncioBroker
from app.infrastructure.broker import broker as default_broker
from app.models.events import RawEvent
from app.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)

CONSECUTIVE_FAILURE_THRESHOLD = 3
DEFAULT_MAX_FETCH_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SECONDS = 1.5
DEFAULT_UNPROCESSED_POLL_SECONDS = 5
DEFAULT_UNPROCESSED_BATCH_LIMIT = 50


# --------------------------------------------------------------------------- #
# Adapter-facing event DTO
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class IngestedEvent:
    """What a FeedAdapter produces, before it becomes an ORM RawEvent row."""

    event_type: str  # matches policy.yaml weight keys, e.g. "adverse_media", "sanctions_hit"
    source: str  # adapter/source name, e.g. "ofac_sdn", "provided_dataset", "injected"
    title: str
    text: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    source_url: str | None = None
    entity_hint: str | None = None  # best-guess entity_id, when the adapter already knows it


def to_orm_event(ingested: IngestedEvent) -> RawEvent:
    """Map an IngestedEvent onto Dev 1's RawEvent ORM model. See module docstring."""
    occurred_at_utc = FeedAdapter.coerce_utc(ingested.occurred_at)
    content_hash = FeedAdapter.compute_content_hash(
        ingested.event_type, ingested.source, ingested.title, ingested.text
    )
    content_blob = json.dumps(
        {
            "event_type": ingested.event_type,
            "source": ingested.source,
            "text": ingested.text,
            "payload": ingested.payload,
            "entity_hint": ingested.entity_hint,
        },
        sort_keys=True,
        default=str,
    )
    return RawEvent(
        content_hash=content_hash,
        content=content_blob,
        source_url=ingested.source_url,
        title=ingested.title,
        occurred_at=occurred_at_utc,
        status="PENDING",
        processed=False,
    )


# --------------------------------------------------------------------------- #
# FeedAdapter ABC
# --------------------------------------------------------------------------- #


class FeedAdapter(ABC):
    """Base class for every ingestion source. Subclasses only implement fetch()."""

    name: str
    schedule_seconds: int

    @abstractmethod
    async def fetch(self) -> list[IngestedEvent]:
        """Return newly observed events. Raise on failure; do not return a partial list silently."""
        raise NotImplementedError

    # -- shared helpers, inherited by every adapter -------------------------

    _TAG_RE = re.compile(r"<[^>]+>")
    _NON_ALNUM_SPACE_RE = re.compile(r"[^A-Z0-9 ]+")
    _MULTI_SPACE_RE = re.compile(r"\s+")

    @staticmethod
    def compute_content_hash(*parts: str) -> str:
        """SHA-256 over `|`-joined parts. Used as RawEvent.content_hash for dedup."""
        joined = "|".join(parts)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    @staticmethod
    def strip_html(raw: str) -> str:
        """Remove tags and unescape entities. Not a security sanitizer -- text only, never rendered."""
        without_tags = FeedAdapter._TAG_RE.sub(" ", raw)
        unescaped = html.unescape(without_tags)
        return FeedAdapter._MULTI_SPACE_RE.sub(" ", unescaped).strip()

    @staticmethod
    def normalize_name(name: str) -> str:
        """Uppercase, strip punctuation, collapse whitespace -- matches SanctionsCache.name_normalized."""
        upper = name.upper()
        alnum_only = FeedAdapter._NON_ALNUM_SPACE_RE.sub(" ", upper)
        return FeedAdapter._MULTI_SPACE_RE.sub(" ", alnum_only).strip()

    @staticmethod
    def coerce_utc(value: datetime) -> datetime:
        """Naive datetimes are assumed UTC; aware datetimes are converted to UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


# --------------------------------------------------------------------------- #
# Registry + per-adapter run state
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class AdapterRunState:
    consecutive_failures: int = 0
    last_success_at: datetime | None = None
    last_error: str | None = None


class AdapterRegistry:
    """Holds every registered adapter plus its operational (not business) state."""

    def __init__(self) -> None:
        self._adapters: dict[str, FeedAdapter] = {}
        self._state: dict[str, AdapterRunState] = {}

    def register(self, adapter: FeedAdapter) -> None:
        if adapter.name in self._adapters:
            raise ValueError(f"adapter {adapter.name!r} already registered")
        self._adapters[adapter.name] = adapter
        self._state[adapter.name] = AdapterRunState()
        log.info("registered adapter %r (schedule_seconds=%d)", adapter.name, adapter.schedule_seconds)

    def all(self) -> list[FeedAdapter]:
        return list(self._adapters.values())

    def state_for(self, name: str) -> AdapterRunState:
        return self._state[name]


# --------------------------------------------------------------------------- #
# Loop A: resilient per-adapter run
# --------------------------------------------------------------------------- #


def persist_events(events: list[IngestedEvent]) -> int:
    """Dedupe by content_hash and persist inside one UnitOfWork. All-or-nothing.

    Public: run_adapter_once() uses this for the normal scheduled path, and
    inject.py's InjectAdapter uses it directly for immediate (non-scheduled)
    persistence -- the one adapter that needs to bypass Loop A's cadence.
    """
    if not events:
        return 0
    new_count = 0
    with UnitOfWork() as uow:
        for ingested in events:
            orm_event = to_orm_event(ingested)
            if uow.events.exists_by_hash(orm_event.content_hash):
                continue
            uow.events.add(orm_event)
            new_count += 1
        uow.commit()
    return new_count


async def run_adapter_once(
    adapter: FeedAdapter,
    registry: AdapterRegistry,
    broker: AsyncioBroker = default_broker,
    *,
    max_attempts: int = DEFAULT_MAX_FETCH_ATTEMPTS,
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
) -> int:
    """Fetch + persist one adapter cycle with retry/backoff. Returns new-events count.

    A failed attempt never persists anything (fetch and persist share one
    try block). After `max_attempts` failures this run, the adapter's
    consecutive_failures counter increments; at CONSECUTIVE_FAILURE_THRESHOLD
    a system.health warning is published so the dashboard can show stale data
    instead of silently going quiet.
    """
    state = registry.state_for(adapter.name)
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            events = await adapter.fetch()
            new_count = persist_events(events)
        except Exception as exc:  # adapters read files/streams that can legitimately fail
            last_exc = exc
            log.warning("%s: fetch attempt %d/%d failed: %s", adapter.name, attempt, max_attempts, exc)
            if attempt < max_attempts:
                await asyncio.sleep(backoff_base_seconds * (2 ** (attempt - 1)))
            continue
        else:
            state.consecutive_failures = 0
            state.last_success_at = datetime.now(timezone.utc)
            state.last_error = None
            if new_count:
                log.info("%s: persisted %d new event(s)", adapter.name, new_count)
            return new_count

    state.consecutive_failures += 1
    state.last_error = str(last_exc)
    log.error(
        "%s: all %d attempts failed (consecutive_failures=%d): %s",
        adapter.name, max_attempts, state.consecutive_failures, state.last_error,
    )
    if state.consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD:
        broker.publish(
            SYSTEM_HEALTH,
            {
                "adapter": adapter.name,
                "status": "stale",
                "consecutive_failures": state.consecutive_failures,
                "last_error": state.last_error,
            },
        )
    return 0


def build_scheduler(registry: AdapterRegistry, broker: AsyncioBroker = default_broker) -> AsyncIOScheduler:
    """One interval job per registered adapter, firing immediately then on its own schedule."""
    scheduler = AsyncIOScheduler()
    for adapter in registry.all():
        scheduler.add_job(
            run_adapter_once,
            trigger="interval",
            seconds=adapter.schedule_seconds,
            args=[adapter, registry, broker],
            id=f"ingestion:{adapter.name}",
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(timezone.utc),
        )
    return scheduler


# --------------------------------------------------------------------------- #
# Loop B: unprocessed-event poll
# --------------------------------------------------------------------------- #


async def poll_unprocessed_events(
    handler: Callable[[RawEvent], Awaitable[None]] | None,
    *,
    poll_seconds: int = DEFAULT_UNPROCESSED_POLL_SECONDS,
    batch_limit: int = DEFAULT_UNPROCESSED_BATCH_LIMIT,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Poll events_raw for unprocessed rows and hand each to `handler`.

    `handler` is a placeholder for Dev 3's traced_pipeline, which doesn't
    exist yet this sprint. With handler=None, unprocessed events are logged,
    not marked processed -- nothing is lost once the real pipeline is wired
    in later this sprint.
    """
    while stop_event is None or not stop_event.is_set():
        with UnitOfWork() as uow:
            pending = uow.events.get_unprocessed(limit=batch_limit)

        if not pending:
            await asyncio.sleep(poll_seconds)
            continue

        if handler is None:
            log.info("%d unprocessed event(s) waiting; no pipeline handler wired yet", len(pending))
        else:
            for event in pending:
                try:
                    await handler(event)
                except Exception:
                    log.exception("pipeline handler failed for event %s", event.id)

        await asyncio.sleep(poll_seconds)


__all__ = [
    "IngestedEvent",
    "to_orm_event",
    "persist_events",
    "FeedAdapter",
    "AdapterRunState",
    "AdapterRegistry",
    "run_adapter_once",
    "build_scheduler",
    "poll_unprocessed_events",
    "CONSECUTIVE_FAILURE_THRESHOLD",
]
