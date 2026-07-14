"""Monitor node — intake and screening.

Responsibilities
----------------
1. Parse ``RawEvent.content`` (JSON blob) to extract event metadata.
2. Resolve the entity from ``entity_hint`` (entity_id) or name search.
3. Run fuzzy sanctions screening (``screen_entity_and_persons``).
4. Start the TraceBuilder and emit an "event" and "screen" node.
5. Route:
   - No entity found               → final_outcome = "screened_out"
   - No screening matches           → final_outcome = "screened_out"
   - Matches found                 → forward to resolver

The monitor is the only node that reads from the DB synchronously (via
UnitOfWork). All subsequent nodes receive whatever the monitor puts in state.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.state import AuditorState
from app.models.events import RawEvent
from app.models.entities import EntityPerson
from app.repositories.unit_of_work import UnitOfWork
from app.services.explainability.trace import TraceBuilder
from app.services.screening import screen_entity_and_persons, ScreeningMatch

log = logging.getLogger(__name__)


def monitor(state: AuditorState) -> AuditorState:
    """Intake and screen a raw event. Synchronous — runs in the LangGraph thread."""
    event_id = state.get("event_id", "")
    log.info("monitor: processing event_id=%s", event_id)

    # ── Step 1: parse RawEvent.content ───────────────────────────────────────
    event_raw = state.get("event_raw", {})
    event_type_hint = event_raw.get("event_type", "unknown")
    entity_hint = event_raw.get("entity_hint")
    event_text = event_raw.get("text", "")
    event_source = event_raw.get("source", "unknown")

    tb = TraceBuilder(event_id=event_id)
    tb.add(
        kind="event",
        label=f"Event ingested ({event_source})",
        detail=f"event_type={event_type_hint}, source={event_source}",
        values={
            "event_id": event_id,
            "event_type": event_type_hint,
            "source": event_source,
            "text_length": len(event_text),
            "entity_hint": entity_hint,
        },
    )

    # ── Step 2: entity resolution ─────────────────────────────────────────────
    entity = None
    persons: list[EntityPerson] = []

    with UnitOfWork() as uow:
        if entity_hint:
            entity = uow.entities.get(entity_hint)

        if entity is None and event_raw.get("payload", {}).get("entity_name"):
            # Fallback: search by name in entities table
            entity_name_hint = event_raw["payload"]["entity_name"]
            all_entities = uow.entities.list()
            for e in all_entities:
                if entity_name_hint.lower() in e.name.lower():
                    entity = e
                    break

        if entity:
            persons = uow.session.query(EntityPerson).filter(
                EntityPerson.entity_id == entity.id
            ).all()

    if entity is None:
        tb.add(
            kind="decision",
            label="No entity resolved",
            detail="Entity hint not found in DB; event screened out.",
            values={"entity_hint": entity_hint},
            outcome="fail",
        )
        state["trace"] = tb
        state["final_outcome"] = "screened_out"
        state["entity_id"] = None
        state["entity_name"] = None
        state["entity_risk_score"] = 0.0
        state["entity_jurisdiction"] = None
        state["entity_persons"] = []
        state["match_score"] = 0.0
        state["screening_matches"] = []
        return state

    entity_persons_dicts = [{"name": p.person_name, "role": p.role} for p in persons]

    # ── Step 3: fuzzy screening ───────────────────────────────────────────────
    screening_result: dict[str, list[ScreeningMatch]] = screen_entity_and_persons(
        entity, persons
    )

    # Flatten to a list of dicts, sorted by score descending
    all_matches: list[dict[str, Any]] = []
    for name, matches in screening_result.items():
        for m in matches:
            all_matches.append({
                "candidate_name": m.candidate_name,
                "matched_name": m.matched_name,
                "score": m.score,
                "source": m.source,
                "list_source": m.list_source,
            })
    all_matches.sort(key=lambda x: x["score"], reverse=True)
    max_score = all_matches[0]["score"] if all_matches else 0.0

    tb.add(
        kind="screen",
        label=f"Fuzzy screening: {len(all_matches)} match(es)",
        detail=(
            f"Top match: '{all_matches[0]['matched_name']}' "
            f"score={all_matches[0]['score']:.0f}" if all_matches
            else "No sanctions/watchlist matches found"
        ),
        values={
            "match_count": len(all_matches),
            "top_score": max_score,
            "entity_name": entity.name,
        },
        outcome="pass" if all_matches else "fail",
    )

    if not all_matches:
        state["trace"] = tb
        state["final_outcome"] = "screened_out"
        state["entity_id"] = entity.id
        state["entity_name"] = entity.name
        state["entity_risk_score"] = entity.risk_score or 0.0
        state["entity_jurisdiction"] = entity.jurisdiction
        state["entity_persons"] = entity_persons_dicts
        state["match_score"] = 0.0
        state["screening_matches"] = []
        return state

    # ── Step 4: populate state and route forward ──────────────────────────────
    state["trace"] = tb
    state["entity_id"] = entity.id
    state["entity_name"] = entity.name
    state["entity_risk_score"] = entity.risk_score or 0.0
    state["entity_jurisdiction"] = entity.jurisdiction
    state["entity_persons"] = entity_persons_dicts
    state["match_score"] = max_score
    state["screening_matches"] = all_matches
    # Initialize resolver fields to safe defaults
    state["llm_verdict_confidence"] = None
    state["llm_degraded"] = False
    state["confidence"] = 0.0
    state["band"] = "dismiss"
    state["final_outcome"] = ""
    state["error"] = None
    return state
