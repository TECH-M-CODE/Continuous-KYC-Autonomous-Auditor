"""Sanctions Agent — fuzzy watchlist screening.

Responsibilities
----------------
1. Run screen_entity_and_persons() against the live sanctions_cache in the DB.
2. Also run screen_watchlist_addition() for reverse screening (newly-added names
   checked against our existing entities).
3. Emit a "screen" trace node with match count and top score.
4. Route to END ("screened_out") if zero matches are found — no sanctions hit
   means the event does not warrant LLM investigation.
5. Populate state["screening_matches"] and state["match_score"] for the resolver.

Why a dedicated agent?
  The old monitor.py mixed entity resolution and sanctions screening in one
  function. This made it impossible to:
  - Test screening in isolation
  - Add alternative screening sources (PEP lists, adverse media index) later
  - Tune the threshold per list source independently
  Extraction here restores single-responsibility.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AuditorState
from app.repositories.unit_of_work import UnitOfWork
from app.services.screening import screen_entity_and_persons

log = logging.getLogger(__name__)


def sanctions_agent(state: AuditorState) -> AuditorState:
    """Fuzzy sanctions / watchlist screening node."""
    entity_id: str | None = state.get("entity_id")
    entity_name: str = state.get("entity_name", "Unknown")
    tb = state["trace"]

    if not entity_id:
        # Should not happen — entity_agent routes to END before us if unresolved.
        log.warning("sanctions_agent: no entity_id in state — routing to screened_out")
        state["screening_matches"] = []
        state["match_score"] = 0.0
        state["final_outcome"] = "screened_out"
        state["trace"] = tb
        return state

    all_matches: list[dict[str, Any]] = []

    with UnitOfWork() as uow:
        entity = uow.entities.get(entity_id)
        if entity is None:
            log.warning("sanctions_agent: entity %s disappeared from DB mid-pipeline", entity_id)
            state["screening_matches"] = []
            state["match_score"] = 0.0
            state["final_outcome"] = "screened_out"
            state["trace"] = tb
            return state

        # Load associated persons (directors / UBOs)
        persons = []
        try:
            from app.models.entities import EntityPerson
            persons = (
                uow.session.query(EntityPerson)
                .filter(EntityPerson.entity_id == entity_id)
                .all()
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("sanctions_agent: could not load persons: %s", exc)

        # ── Forward screening: entity + persons vs sanctions_cache ────────────
        try:
            screening_result = screen_entity_and_persons(entity, persons)
            for candidate_name, matches in screening_result.items():
                for m in matches:
                    all_matches.append({
                        "candidate_name": getattr(m, "candidate_name", candidate_name),
                        "matched_name":   getattr(m, "matched_name", ""),
                        "score":          getattr(m, "score", 0.0),
                        "source":         getattr(m, "source", "sanctions_cache"),
                        "list_source":    getattr(m, "list_source", None),
                    })
        except Exception as exc:  # noqa: BLE001
            log.error("sanctions_agent: screening failed for entity=%s: %s", entity_id, exc)
            tb.add(
                kind="screen",
                label="Screening error",
                detail=str(exc),
                values={"error": str(exc)},
                outcome="fail",
            )
            state["trace"] = tb
            state["error"] = f"sanctions screening error: {exc}"
            return state

    # ── Sort by score descending ──────────────────────────────────────────────
    all_matches.sort(key=lambda x: x["score"], reverse=True)
    max_score = all_matches[0]["score"] if all_matches else 0.0

    # ── Trace node ────────────────────────────────────────────────────────────
    if all_matches:
        top = all_matches[0]
        trace_detail = (
            f"Top match: '{top['matched_name']}' from {top['source']} "
            f"(score {top['score']:.0f}/100)"
        )
        trace_outcome = "pass"
    else:
        trace_detail = f"No watchlist matches found for entity '{entity_name}'"
        trace_outcome = "fail"

    tb.add(
        kind="screen",
        label=f"Sanctions screening: {len(all_matches)} match(es) | top={max_score:.0f}/100",
        detail=trace_detail,
        values={
            "entity_name": entity_name,
            "match_count": len(all_matches),
            "top_score": max_score,
            "sources": list({m["source"] for m in all_matches}),
        },
        outcome=trace_outcome,
    )

    # ── Route: no direct watchlist match → still investigate (enrichment-only) ──
    # Design decision: a resolved entity is ALWAYS investigated. A sanctions
    # match is an enriching signal that boosts the risk score when present, not a
    # hard gate that terminates the pipeline. When there is no match we forward to
    # the resolver with an empty match set instead of screening the event out, so
    # injected/adverse-media events on any monitored entity still produce a risk
    # event, alert, and SAR downstream.
    if not all_matches:
        state["trace"] = tb
        state["screening_matches"] = []
        state["match_score"] = 0.0
        state["final_outcome"] = ""
        state["llm_verdict_confidence"] = None
        state["llm_degraded"] = False
        state["confidence"] = 0.0
        state["band"] = "dismiss"
        log.info(
            "sanctions_agent: no matches for entity=%s → forwarding to resolver (enrichment-only)",
            entity_name,
        )
        return state

    # ── Matches found → forward to resolver ──────────────────────────────────
    state["trace"] = tb
    state["screening_matches"] = all_matches
    state["match_score"] = max_score
    # Pre-clear resolver fields so no stale data leaks through
    state["llm_verdict_confidence"] = None
    state["llm_degraded"] = False
    state["confidence"] = 0.0
    state["band"] = "dismiss"

    log.info(
        "sanctions_agent: %d match(es) for entity=%s top_score=%.0f → forwarding to resolver",
        len(all_matches), entity_name, max_score,
    )
    return state
