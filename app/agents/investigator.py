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

import logging
from pydantic import BaseModel

from app.agents.state import AuditorState
from app.agents.prompts.investigator_prompts import KNOWN_EVENT_TYPES
from app.repositories.unit_of_work import UnitOfWork
from app.services.scoring.policy import get_policy

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

    # ── Deterministic classification (no LLM on the hot path) ───────────────
    # event_type comes from the ingested signal itself (the inject form / adapter
    # already set it), and severity is derived from the enrichment hit counts.
    # This removes an LLM round-trip from every event; the SAR narrative in the
    # reporter node remains the single LLM-authored artifact. The old LLM
    # classify call added ~15-20s per event and degraded frequently.
    event_raw = state.get("event_raw", {})
    news_ctx = state.get("news_context") or {}
    structured = news_ctx.get("structured_data") or {}

    event_type = event_raw.get("event_type", _DEFAULT_EVENT_TYPE)
    if event_type not in KNOWN_EVENT_TYPES:
        event_type = _DEFAULT_EVENT_TYPE

    _sanctions = structured.get("sanctions_hits", 0)
    _fraud = structured.get("financial_fraud_hits", 0)
    _adverse = structured.get("adverse_media_hits", 0)
    _reg = structured.get("regulatory_mentions", 0)
    if _sanctions or state.get("screening_matches"):
        severity = 0.95
    elif _fraud:
        severity = 0.8
    elif _adverse >= 3 or _reg > 1:
        severity = 0.6
    else:
        severity = _DEFAULT_SEVERITY

    evidence_summary = structured.get("summary") or (
        f"Automated screening flagged {entity_name} for "
        f"{event_type.replace('_', ' ')}."
    )

    tb.add(
        kind="classify",
        label=f"Classified: {event_type} (severity {severity:.2f})",
        detail=evidence_summary,
        values={
            "event_type": event_type,
            "severity": severity,
            "llm_ok": False,
            "deterministic": True,
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

        # Retrieve structured data from the News Agent. When the enrichment LLM
        # degrades (timeout / schema miss) structured_data is None, so guard it.
        news_context = state.get("news_context") or {}
        structured = news_context.get("structured_data") or {}

        adverse_media = structured.get("adverse_media_hits", 0)
        fraud = structured.get("financial_fraud_hits", 0)
        sanctions = structured.get("sanctions_hits", 0)
        reg = structured.get("regulatory_mentions", 0)

        log.info(f"investigator: Found {adverse_media} adverse media articles.")
        log.info(f"investigator: Found {fraud} financial fraud reports.")
        log.info(f"investigator: Found {sanctions} sanctions hits.")

        # A sanctions screening match is itself a strong signal even when the news
        # enrichment came back empty.
        has_sanctions_match = bool(state.get("screening_matches"))

        # Dynamic risk from enriched hits when we have them...
        dynamic_base_score = 0
        if sanctions > 0 or has_sanctions_match:
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

        # ...otherwise fall back to the event's own type. Every event that reaches
        # the investigator is an adverse signal, so it must carry a meaningful base
        # score even when enrichment is unavailable (degraded LLM).
        event_type_floor = {
            "sanctions_hit": 90,
            "sanctions": 90,
            "financial_fraud": 75,
            "transaction_anomaly": 50,
            "structuring": 50,
            "adverse_media": 55,
            "pep_update": 45,
        }.get((event_type or "").lower(), 40)
        dynamic_base_score = max(dynamic_base_score, event_type_floor)
        # Delta is finalized against the entity's actual DB score below.
        score_delta_val = 0.0

        with UnitOfWork() as uow:
            from app.models.risk import RiskEvent
            import uuid
            from datetime import datetime, timezone
            
            # Update entity score directly in DB
            entity = uow.entities.get(entity_id)
            if entity:
                old_score = entity.risk_score or 0.0
                # An adverse event never lowers an entity's standing risk: take the
                # higher of the current score and this event's computed base, so a
                # degraded enrichment can't tank a known high-risk entity.
                entity.risk_score = float(max(old_score, dynamic_base_score))
                score_delta_val = entity.risk_score - old_score

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
