"""Entity Resolution Agent.

Responsibilities
----------------
1. Look up entity from entity_hint (entity_id) in the DB — O(1) direct path.
2. Fuzzy name-match across all entities using rapidfuzz if hint is absent
   or yields no result — handles aliases, abbreviated names, reordered tokens.
3. Load associated EntityPerson records (directors, UBOs).
4. Emit a "resolve" trace node with resolution confidence.
5. Route to END ("screened_out") if no entity can be resolved — the pipeline
   never processes events that cannot be tied to a monitored entity.

Why fuzzy here and not in monitor?
  The old monitor.py used a substring check (`hint in name`) which fails on:
    - Abbreviated names: "Tesla" vs "Tesla Motors Inc."
    - Reordered tokens: "John Smith" vs "Smith, John"
    - Partial alias: "Goldman" vs "Goldman Sachs Group Inc."
  rapidfuzz.token_sort_ratio handles all three cases correctly.
"""
from __future__ import annotations

import logging
from typing import Any

from rapidfuzz import process, fuzz

from app.agents.state import AuditorState
from app.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)

# Minimum fuzzy score (0–100) to accept a name-based entity match.
# 75 is the same threshold used by the sanctions screening service.
_FUZZY_THRESHOLD = 75


def entity_agent(state: AuditorState) -> AuditorState:
    """Entity resolution node — DB lookup + optional fuzzy name match."""
    event_raw: dict[str, Any] = state.get("event_raw", {})
    tb = state["trace"]

    entity_hint: str | None = event_raw.get("entity_hint")       # direct entity_id
    name_hint: str = (
        event_raw.get("payload", {}).get("entity_name", "")
        or event_raw.get("payload", {}).get("sanctioned_name", "")
        or event_raw.get("entity_name", "")
    )

    entity = None
    persons = []
    resolution_confidence = 0.0
    resolution_method = "none"

    with UnitOfWork() as uow:
        # ── 1. Direct ID lookup ───────────────────────────────────────────────
        if entity_hint:
            entity = uow.entities.get(entity_hint)
            if entity:
                resolution_confidence = 1.0
                resolution_method = "direct_id"
                log.info("entity_agent: direct match entity_id=%s", entity.id)

        # ── 2. Fuzzy name match ───────────────────────────────────────────────
        if entity is None and name_hint:
            all_entities = uow.entities.list()
            if all_entities:
                choices = {e.id: e.name for e in all_entities}
                result = process.extractOne(
                    name_hint,
                    choices,
                    scorer=fuzz.token_sort_ratio,
                    score_cutoff=_FUZZY_THRESHOLD,
                )
                if result:
                    matched_name, score, matched_id = result
                    entity = uow.entities.get(matched_id)
                    resolution_confidence = score / 100.0
                    resolution_method = f"fuzzy_name (score={score:.0f})"
                    log.info(
                        "entity_agent: fuzzy match '%s' → '%s' score=%.0f",
                        name_hint, matched_name, score,
                    )

        # ── 3. Load persons ───────────────────────────────────────────────────
        if entity:
            try:
                from app.models.entities import EntityPerson
                persons = (
                    uow.session.query(EntityPerson)
                    .filter(EntityPerson.entity_id == entity.id)
                    .all()
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("entity_agent: could not load persons: %s", exc)

    # ── 4a. Failed resolution → screened out ─────────────────────────────────
    if entity is None:
        tb.add(
            kind="decision",
            label="Entity not resolved — event dismissed",
            detail=(
                f"No entity found for hint='{entity_hint}' / name='{name_hint}'. "
                "Event cannot be attributed to a monitored entity."
            ),
            values={
                "entity_hint": entity_hint,
                "name_hint": name_hint,
                "resolution_method": resolution_method,
            },
            outcome="fail",
        )
        state["trace"] = tb
        state["final_outcome"] = "screened_out"
        state["entity_id"] = None
        state["entity_name"] = None
        state["entity_risk_score"] = 0.0
        state["entity_jurisdiction"] = None
        state["entity_persons"] = []
        state["screening_matches"] = []
        state["match_score"] = 0.0
        log.info(
            "entity_agent: SCREENED OUT — no entity for hint=%s name=%s",
            entity_hint, name_hint,
        )
        return state

    # ── 4b. Success → populate state ─────────────────────────────────────────
    persons_dicts = [
        {"name": p.person_name, "role": p.role}
        for p in persons
    ]

    tb.add(
        kind="resolve",
        label=f"Entity resolved: {entity.name}",
        detail=(
            f"Method: {resolution_method} | "
            f"Confidence: {resolution_confidence:.0%} | "
            f"Risk score: {entity.risk_score:.1f} | "
            f"Persons: {len(persons)}"
        ),
        values={
            "entity_id": entity.id,
            "entity_name": entity.name,
            "resolution_confidence": resolution_confidence,
            "resolution_method": resolution_method,
            "risk_score": entity.risk_score or 0.0,
            "jurisdiction": entity.jurisdiction,
            "person_count": len(persons),
        },
        outcome="pass",
    )

    state["trace"] = tb
    state["entity_id"] = entity.id
    state["entity_name"] = entity.name
    state["entity_risk_score"] = entity.risk_score or 0.0
    state["entity_jurisdiction"] = entity.jurisdiction
    state["entity_persons"] = persons_dicts
    # Clear any stale routing fields
    state["final_outcome"] = ""
    state["error"] = None

    log.info(
        "entity_agent: resolved entity=%s confidence=%.0f%% persons=%d",
        entity.name, resolution_confidence * 100, len(persons),
    )
    return state
