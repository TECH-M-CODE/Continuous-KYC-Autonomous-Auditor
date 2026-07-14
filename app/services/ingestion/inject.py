"""InjectAdapter: hand-crafted event injection -- the demo trigger button
(and Sprint 3's red-team entry point).

Unlike the other adapters, InjectAdapter doesn't poll anything. External
callers (eventually a POST /api/admin/inject route -- see this module's
note on why that route isn't added here) call inject_now(), which builds
an IngestedEvent and persists it immediately via base.py's persist_events(),
the same dedup+persist path every scheduled adapter uses. Its fetch()
(invoked by Loop A on its own schedule, since it's still a FeedAdapter for
registry/scheduler consistency) only drains anything queued but not yet
persisted -- a safety net, not the primary path.

is_drill has no events_raw column (same situation as event_type/payload,
see base.py's module docstring) -- it's folded into IngestedEvent.payload.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.ingestion.base import FeedAdapter, IngestedEvent, persist_events

log = logging.getLogger(__name__)

DEFAULT_SCHEDULE_SECONDS = 3600  # inert on its own schedule; inject_now() is the real path


class InjectAdapter(FeedAdapter):
    """Manual event injection. See module docstring."""

    name = "inject"
    schedule_seconds = DEFAULT_SCHEDULE_SECONDS

    def __init__(self) -> None:
        self._pending: list[IngestedEvent] = []

    async def fetch(self) -> list[IngestedEvent]:
        drained, self._pending = self._pending, []
        if drained:
            log.info("inject: draining %d event(s) queued since last Loop A tick", len(drained))
        return drained

    def inject_now(
        self,
        event_type: str,
        title: str,
        text: str,
        entity_hint: str | None = None,
        payload: dict[str, Any] | None = None,
        is_drill: bool = False,
        occurred_at: datetime | None = None,
    ) -> IngestedEvent | None:
        """Build and immediately persist a hand-crafted event.

        Returns the IngestedEvent that was persisted, or None if an
        identical injection (same event_type/source/title/text) already
        exists and was deduped by content_hash.
        """
        ingested = IngestedEvent(
            event_type=event_type,
            source="injected",
            title=title,
            text=text,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            payload={**(payload or {}), "is_drill": is_drill},
            entity_hint=entity_hint,
        )

        self._pending.append(ingested)
        new_count = persist_events([ingested])
        self._pending.remove(ingested)

        if new_count == 0:
            log.info("inject: %r deduped, identical injection already persisted", title)
            return None

        log.info("inject: persisted %r (event_type=%s, is_drill=%s)", title, event_type, is_drill)
        return ingested
