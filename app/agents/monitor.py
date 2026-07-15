"""Monitor node — raw event parsing and TraceBuilder initialization.

Sprint 4 refactor: entity resolution and sanctions screening are now
dedicated agents (entity_agent, sanctions_agent). Monitor's single job
is to parse the raw event JSON blob and initialize the TraceBuilder
so every downstream node has a valid trace to append to.

Pipeline order:
  monitor → news_agent → entity_agent → sanctions_agent → resolver → investigator → reporter

Why keep monitor separate?
  Parsing the event and initializing the TraceBuilder is always the first
  step, regardless of which downstream path is taken. Keeping it separate
  means every node receives a guaranteed non-None ``state["trace"]``.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AuditorState
from app.services.explainability.trace import TraceBuilder

log = logging.getLogger(__name__)


def monitor(state: AuditorState) -> AuditorState:
    """Parse raw event and initialize TraceBuilder. Sync, no DB access."""
    event_id: str = state.get("event_id", "")
    event_raw: dict[str, Any] = state.get("event_raw", {})

    event_type = event_raw.get("event_type", "unknown")
    source = event_raw.get("source", "unknown")
    entity_hint = event_raw.get("entity_hint")
    text = event_raw.get("text", "")

    log.info(
        "monitor: event_id=%s type=%s source=%s entity_hint=%s",
        event_id, event_type, source, entity_hint,
    )

    tb = TraceBuilder(event_id=event_id)
    tb.add(
        kind="event",
        label=f"Event ingested ({source})",
        detail=f"event_type={event_type} | source={source} | text_len={len(text)}",
        values={
            "event_id": event_id,
            "event_type": event_type,
            "source": source,
            "text_length": len(text),
            "entity_hint": entity_hint,
        },
    )

    state["trace"] = tb
    state["news_context"] = None   # populated by news_agent
    state["final_outcome"] = ""
    state["error"] = None
    return state
