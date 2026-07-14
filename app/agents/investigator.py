"""Investigator node — event classification and risk scoring.

Responsibilities
----------------
1. Call LLM Gateway: task_tag="classify_event" to get event_type + severity.
2. Apply ``compute_delta()`` + ``apply_delta()`` to update the entity risk score.
3. Gather corroborating evidence from the DB (other recent risk events).
4. Emit "classify" and "score" nodes in the TraceBuilder.
5. Always routes to reporter (the investigator never terminates the pipeline).
"""

from __future__ import annotations

import asyncio
import logging
from pydantic import BaseModel

from app.agents.state import AuditorState
from app.agents.prompts.investigator_prompts import build_investigator_prompt, KNOWN_EVENT_TYPES
from app.repositories.unit_of_work import UnitOfWork
from app.services.scoring.policy import get_policy
from app.services.scoring.rule_engine import compute_delta, apply_delta

log = logging.getLogger(__name__)

_DEFAULT_SEVERITY = 0.7
_DEFAULT_EVENT_TYPE = "adverse_media"


# ── LLM response schema ──────────────────────────────────────────────────────

class ClassifyEventResult(BaseModel):
    event_type: str
    severity: float
    evidence_summary: str


# ── Node ────────────────────────────────────────────────────────────────────

def investigator(state: AuditorState, *, gateway) -> AuditorState:
    """Investigator node. ``gateway`` is injected by supervisor."""
    entity_id = state.get("entity_id", "")
    entity_name = state.get("entity_name", "Unknown")
    log.info("investigator: entity=%s", entity_name)

    tb = state["trace"]

    # ── LLM call: classify ─────────────────────────────────────────────────
    event_raw = state.get("event_raw", {})
    prompt = build_investigator_prompt(
        entity_name=entity_name,
        event_type_hint=event_raw.get("event_type", "unknown"),
        event_text=event_raw.get("text", ""),
        event_source=event_raw.get("source", "unknown"),
        screening_matches=state.get("screening_matches", []),
    )

    result = asyncio.get_event_loop().run_until_complete(
        gateway.complete(prompt, schema=ClassifyEventResult, task_tag="classify_event")
    )

    if result.ok and result.data:
        classify: ClassifyEventResult = result.data
        # Validate event_type is in policy
        event_type = (
            classify.event_type if classify.event_type in KNOWN_EVENT_TYPES
            else _DEFAULT_EVENT_TYPE
        )
        severity = max(0.0, min(1.0, classify.severity))
        evidence_summary = classify.evidence_summary
    else:
        event_type = event_raw.get("event_type", _DEFAULT_EVENT_TYPE)
        if event_type not in KNOWN_EVENT_TYPES:
            event_type = _DEFAULT_EVENT_TYPE
        severity = _DEFAULT_SEVERITY
        evidence_summary = "LLM classification unavailable; defaults applied."
        log.warning("investigator: LLM classify degraded for entity=%s", entity_name)

    tb.add(
        kind="classify",
        label=f"Classified: {event_type} (severity {severity:.2f})",
        detail=evidence_summary,
        values={
            "event_type": event_type,
            "severity": severity,
            "llm_ok": result.ok,
            "llm_degraded": result.degraded,
        },
        outcome="pass",
    )

    # ── Risk scoring via rule engine ──────────────────────────────────────────
    jf_val = 1.0  # safe default if policy load fails
    score_delta_val = 0.0
    new_score = state.get("entity_risk_score", 0.0)
    risk_band = "UNKNOWN"

    try:
        policy = get_policy()
        jurisdiction = state.get("entity_jurisdiction") or "default"
        jf_val = policy.jurisdiction_factors.get(jurisdiction, policy.jurisdiction_factors.get("default", 1.0))

        score_delta = compute_delta(
            event_type=event_type,
            severity=severity,
            jurisdiction_factor=jf_val,
            policy=policy,
        )

        with UnitOfWork() as uow:
            new_score = apply_delta(
                entity_id=entity_id,
                score_delta=score_delta,
                uow=uow,
                event_id=state.get("event_id"),
                event_category=event_type.upper(),
                reasoning=evidence_summary,
                policy=policy,
            )
            # Read the resolved band back
            entity = uow.entities.get(entity_id)
            risk_band = entity.risk_band if entity else "LOW"
            uow.commit()

        tb.add(
            kind="score",
            label=f"Risk score: {new_score:.1f} ({risk_band})",
            detail=(
                f"Δ={score_delta.delta:+.2f} "
                f"(weight={score_delta.weight:.1f} × severity={severity:.2f} × jf={jf_val:.2f})"
            ),
            values={
                "event_type": event_type,
                "weight": score_delta.weight,
                "severity": severity,
                "jurisdiction_factor": jf_val,
                "delta": score_delta.delta,
                "score_after": new_score,
                "risk_band": risk_band,
            },
            outcome="pass",
        )
        score_delta_val = score_delta.delta

    except Exception as exc:  # noqa: BLE001
        log.error("investigator: scoring failed for entity=%s: %s", entity_id, exc)
        tb.add(
            kind="score",
            label="Scoring failed",
            detail=str(exc),
            values={"error": str(exc)},
            outcome="fail",
        )


    # ── Gather evidence items for the reporter ────────────────────────────────
    evidence = [
        {
            "source": m.get("source", "unknown"),
            "snippet": (
                f"Fuzzy match '{m.get('matched_name', '?')}' "
                f"(score {m.get('score', 0):.0f}/100)"
            ),
            "url": None,
            "relevance": round(m.get("score", 0) / 100.0, 4),
        }
        for m in state.get("screening_matches", [])[:5]
    ]

    if evidence_summary:
        evidence.insert(0, {
            "source": event_raw.get("source", "AI Investigation"),
            "snippet": evidence_summary,
            "url": event_raw.get("source_url"),
            "relevance": round(min(severity + 0.1, 1.0), 4),
        })

    state["event_type"] = event_type
    state["severity"] = severity
    state["jurisdiction_factor"] = jf_val
    state["score_delta"] = score_delta_val
    state["new_risk_score"] = new_score
    state["risk_band"] = risk_band
    state["evidence"] = evidence
    state["investigation_summary"] = evidence_summary
    state["trace"] = tb
    return state
