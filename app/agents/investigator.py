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

    # ── Risk scoring ───────────────────────────────────────────────────────────
    # Two distinct numbers, deliberately kept separate:
    #   * event_score — the severity of THIS event. Drives the alert priority and
    #     the risk_event severity. Derived from the ingested event type plus
    #     severity keywords in the event text, so different injects produce
    #     genuinely different bands (LOW..CRITICAL) instead of everything
    #     collapsing onto the entity's pre-seeded high score.
    #   * entity.risk_score — the entity's cumulative standing risk, which only
    #     ratchets up (an adverse event never lowers a known-risky entity).
    jf_val = 1.0
    score_delta_val = 0.0
    new_score = state.get("entity_risk_score", 0.0)
    risk_band = "LOW"
    risk_event_id: str | None = None

    def _band_of(score: float) -> str:
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        return "LOW"

    try:
        policy = get_policy()
        jurisdiction = state.get("entity_jurisdiction") or "default"
        jf_val = policy.jurisdiction_factors.get(jurisdiction, policy.jurisdiction_factors.get("default", 1.0))

        # Base severity from the injected/ingested event type.
        _TYPE_BASE = {
            "sanctions_hit": 90,
            "sanctions": 90,
            "financial_fraud": 78,
            "transaction_anomaly": 48,
            "structuring": 55,
            "adverse_media": 30,   # modulated by text severity below
            "pep_update": 42,
        }
        event_score = _TYPE_BASE.get((event_type or "").lower(), 35)

        # Modulate by severity keywords in the event's own text, so what the
        # analyst types in the inject form actually changes the outcome.
        event_text = (event_raw.get("text") or "").lower()
        _HIGH_KW = ("launder", "fraud", "terror", "sanction", "ofac", "bribery",
                    "embezzle", "trafficking", "corrupt", "evasion", "smuggl")
        _MED_KW = ("investigation", "probe", "scrutiny", "lawsuit", "penalty",
                   "fine", "violation", "misconduct", "regulat", "complian", "allegation")
        if any(k in event_text for k in _HIGH_KW):
            event_score = max(event_score, 75)
        elif any(k in event_text for k in _MED_KW):
            event_score = max(event_score, 50)

        # A real sanctions/watchlist screening match is always critical.
        if state.get("screening_matches"):
            event_score = 90

        event_band = _band_of(event_score)
        log.info("investigator: event_score=%d band=%s (type=%s)", event_score, event_band, event_type)

        with UnitOfWork() as uow:
            from app.models.risk import RiskEvent
            import uuid
            from datetime import datetime, timezone

            entity = uow.entities.get(entity_id)
            if entity:
                old_score = entity.risk_score or 0.0
                # Cumulative entity risk only ratchets up; never tank a known entity.
                entity.risk_score = float(max(old_score, event_score))
                entity.risk_band = _band_of(entity.risk_score)
                score_delta_val = round(entity.risk_score - old_score, 1)  # >= 0

                risk_event = RiskEvent(
                    id=str(uuid.uuid4()),
                    entity_id=entity_id,
                    event_id=state.get("event_id"),
                    event_category=event_type.upper(),
                    delta=score_delta_val,
                    severity=event_band,          # this event's own severity
                    score_after=entity.risk_score,
                    reasoning=evidence_summary,
                    created_at=datetime.now(timezone.utc),
                )
                uow.session.add(risk_event)

                new_score = entity.risk_score     # cumulative (entity display)
                risk_band = event_band            # this event's band (alert priority)
                risk_event_id = risk_event.id

                log.info("investigator: entity risk %.0f -> %.0f (event %s)", old_score, new_score, event_band)
                uow.commit()

        tb.add(
            kind="score",
            label=f"Event risk: {event_score} ({event_band}) · Entity now {new_score:.0f}",
            detail=(
                f"Event severity {event_score}/100 ({event_band}) drives this alert; "
                f"entity cumulative risk is {new_score:.0f} ({_band_of(new_score)})."
            ),
            values={
                "event_type": event_type,
                "event_score": event_score,
                "event_band": event_band,
                "entity_score": new_score,
                "delta": score_delta_val,
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
