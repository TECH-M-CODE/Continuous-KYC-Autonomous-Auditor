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

    # See resolver.py's comment: this node runs in asyncio.to_thread()'s worker
    # thread, which has no event loop -- asyncio.run() creates one for this call.
    # Run async gateway in the worker thread's own event loop.
    result = asyncio.run(
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

    # ── Risk scoring via dataset hits ──────────────────────────────────────────
    jf_val = 1.0  
    score_delta_val = 0.0
    new_score = state.get("entity_risk_score", 0.0)
    risk_band = "UNKNOWN"
    risk_event_id: str | None = None

    try:
        policy = get_policy()
        jurisdiction = state.get("entity_jurisdiction") or "default"
        jf_val = policy.jurisdiction_factors.get(jurisdiction, policy.jurisdiction_factors.get("default", 1.0))

        # Retrieve structured data from News Agent
        news_context = state.get("news_context", {})
        structured = news_context.get("structured_data", {})
        
        adverse_media = structured.get("adverse_media_hits", 0)
        fraud = structured.get("financial_fraud_hits", 0)
        sanctions = structured.get("sanctions_hits", 0)
        reg = structured.get("regulatory_mentions", 0)
        
        log.info(f"investigator: Found {adverse_media} adverse media articles.")
        log.info(f"investigator: Found {fraud} financial fraud reports.")
        log.info(f"investigator: Found {sanctions} sanctions hits.")
        
        # Dynamic Risk Calculation based on datasets
        dynamic_base_score = 0
        if sanctions > 0:
            dynamic_base_score = 90  # Critical
            log.info("investigator: Entity with sanctions -> Critical Risk")
        elif fraud > 0:
            dynamic_base_score = 75  # High
            log.info("investigator: Entity with financial fraud -> High Risk")
        elif adverse_media >= 3 or reg > 1:
            dynamic_base_score = 50  # Medium
            log.info("investigator: Entity with repeated adverse media -> Medium Risk")
        elif adverse_media > 0 or reg > 0:
            dynamic_base_score = 30  # Low-Medium
            log.info("investigator: Entity with few findings -> Low Risk")
        else:
            dynamic_base_score = 10  # Low
            log.info("investigator: Entity with no meaningful findings -> Low Risk")
            
        # Calculate delta from current score
        score_delta_val = dynamic_base_score - new_score

        with UnitOfWork() as uow:
            from app.models.risk import RiskEvent
            import uuid
            from datetime import datetime, timezone
            
            # Update entity score directly in DB
            entity = uow.entities.get(entity_id)
            if entity:
                old_score = entity.risk_score
                entity.risk_score = dynamic_base_score
                
                # Determine risk band
                if entity.risk_score >= 80:
                    entity.risk_band = "CRITICAL"
                elif entity.risk_score >= 60:
                    entity.risk_band = "HIGH"
                elif entity.risk_score >= 40:
                    entity.risk_band = "MEDIUM"
                else:
                    entity.risk_band = "LOW"
                    
                # Create RiskEvent
                risk_event = RiskEvent(
                    id=str(uuid.uuid4()),
                    entity_id=entity_id,
                    event_id=state.get("event_id"),
                    event_category=event_type.upper(),
                    delta=score_delta_val,
                    severity=risk_band,
                    score_after=entity.risk_score,
                    reasoning=evidence_summary,
                    created_at=datetime.now(timezone.utc)
                )
                uow.session.add(risk_event)
                
                new_score = entity.risk_score
                risk_band = entity.risk_band
                risk_event_id = risk_event.id
                
                log.info(f"investigator: Risk updated from {old_score} -> {new_score}.")
                uow.commit()

        tb.add(
            kind="score",
            label=f"Risk score: {new_score:.1f} ({risk_band})",
            detail=(
                f"Dynamic Score based on hits: AdverseMedia={adverse_media}, Fraud={fraud}, Sanctions={sanctions}"
            ),
            values={
                "event_type": event_type,
                "severity": severity,
                "delta": score_delta_val,
                "score_after": new_score,
                "risk_band": risk_band,
            },
            outcome="pass",
        )

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
    state["risk_event_id"] = risk_event_id
    state["evidence"] = evidence
    state["investigation_summary"] = evidence_summary
    state["trace"] = tb
    return state
