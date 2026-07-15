"""Reporter node — final persistence, SAR generation, and event publishing.

Responsibilities
----------------
1. Call LLM Gateway: task_tag="sar_narrative" to generate the SAR narrative + citations.
2. Determine alert priority from the risk band.
3. Persist: Alert (with serialized DecisionTrace), SARDraft, and 3 AuditLog entries.
4. Mark the original RawEvent as processed (processed=True, status="PROCESSED").
5. Publish ``ALERT_NEW`` and ``SAR_READY`` to the broker.
6. Finalize the DecisionTrace and set ``final_outcome``.

All DB writes are in a single UnitOfWork so they are fully atomic — if any
write fails, nothing is committed and the RawEvent stays unprocessed for retry.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pydantic import BaseModel

from app.agents.state import AuditorState
from app.agents.prompts.reporter_prompts import build_reporter_prompt
from app.infrastructure.broker import broker, ALERT_NEW, SAR_READY
from app.models.events import Alert
from app.repositories.unit_of_work import UnitOfWork
from app.services.audit_service import append_audit
from app.services.sar_service import create_sar_draft

log = logging.getLogger(__name__)

_BAND_TO_PRIORITY = {
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}

_RISK_BAND_TO_OUTCOME = {
    "LOW": "alert_medium",
    "MEDIUM": "alert_medium",
    "HIGH": "alert_high",
    "CRITICAL": "alert_critical",
}


# ── LLM response schema ──────────────────────────────────────────────────────

class _Citation(BaseModel):
    citation: str
    passage: str

class SARNarrativeResult(BaseModel):
    narrative: str
    citations: list[_Citation]


# ── Node ────────────────────────────────────────────────────────────────────

def reporter(state: AuditorState, *, gateway) -> AuditorState:
    """Reporter node. ``gateway`` is injected by supervisor."""
    entity_id = state.get("entity_id", "")
    entity_name = state.get("entity_name", "Unknown")
    risk_band = state.get("risk_band", "MEDIUM")
    log.info("reporter: entity=%s band=%s", entity_name, risk_band)

    tb = state["trace"]

    # ── LLM call: SAR narrative ───────────────────────────────────────────────
    prompt = build_reporter_prompt(
        entity_name=entity_name,
        entity_jurisdiction=state.get("entity_jurisdiction"),
        event_type=state.get("event_type", "adverse_media"),
        severity=state.get("severity", 0.7),
        evidence_summary=state.get("investigation_summary", ""),
        screening_matches=state.get("screening_matches", []),
        confidence=state.get("confidence", 0.5),
        risk_band=risk_band,
        new_risk_score=state.get("new_risk_score", 0.0),
    )

    # See resolver.py's comment: this node runs in asyncio.to_thread()'s worker
    # thread, which has no event loop -- asyncio.run() creates one for this call.
    result = asyncio.run(
        gateway.complete(prompt, schema=SARNarrativeResult, task_tag="sar_narrative")
    )

    if result.ok and result.data:
        sar_data: SARNarrativeResult = result.data
        narrative = sar_data.narrative
        citations = [{"citation": c.citation, "passage": c.passage} for c in sar_data.citations]
    else:
        narrative = (
            f"Automated SAR for {entity_name}. Risk event classification: "
            f"{state.get('event_type', 'unknown')}. "
            f"Risk score updated to {state.get('new_risk_score', 0):.1f} ({risk_band}). "
            "LLM narrative generation was unavailable; human review required."
        )
        citations = []
        log.warning("reporter: SAR narrative LLM degraded for entity=%s", entity_name)

    # ── Determine alert priority ──────────────────────────────────────────────
    # risk_band can be "UNKNOWN" (investigator's scoring step failed -- e.g. an
    # event_type absent from policy.yaml's weights) or any other unrecognized
    # value. Alert.band has a DB CHECK constraint restricted to low/medium/
    # high/critical, so an unsanitized value here would crash this insert and
    # silently drop the whole alert -- fall back to MEDIUM like priority does.
    db_band = risk_band.upper() if risk_band.upper() in _BAND_TO_PRIORITY else "MEDIUM"
    priority = _BAND_TO_PRIORITY.get(risk_band.upper(), "MEDIUM")
    final_outcome = _RISK_BAND_TO_OUTCOME.get(risk_band.upper(), "alert_medium")

    # ── Finalize the decision trace ───────────────────────────────────────────
    tb.add(
        kind="decision",
        label=f"Alert generated: {priority}",
        detail=f"SAR narrative produced. Priority: {priority}, Band: {risk_band}.",
        values={
            "priority": priority,
            "risk_band": risk_band,
            "new_risk_score": state.get("new_risk_score"),
            "confidence": state.get("confidence"),
            "sar_citations_count": len(citations),
        },
        outcome="pass",
    )

    decision_trace = tb.finalize(
        final_outcome=final_outcome,
        counterfactual=(
            f"Had the entity's risk score been below 40, the event would have been dismissed. "
            f"The {state.get('event_type', 'unknown')} event added "
            f"{state.get('score_delta', 0):.2f} points."
        ),
    )

    trace_json = decision_trace.model_dump_json()

    # ── Atomic DB write ───────────────────────────────────────────────────────
    alert_id: str | None = None
    sar_id: str | None = None

    try:
        with UnitOfWork() as uow:
            # 1. Create Alert
            alert = Alert(
                entity_id=entity_id,
                trigger_event_id=state.get("risk_event_id"),
                priority=priority,
                status="OPEN",
                band=db_band,
                trace=trace_json,
            )
            uow.alerts.add(alert)
            uow.session.flush()   # materialize alert.id before SAR links to it
            alert_id = alert.id

            # 2. Audit: risk updated
            append_audit(
                action="ENTITY_RISK_UPDATED",
                payload={
                    "score_delta": state.get("score_delta", 0),
                    "new_score": state.get("new_risk_score", 0),
                    "risk_band": risk_band,
                    "event_id": state.get("event_id"),
                },
                uow=uow,
                entity_id=entity_id,
            )

            # 3. Audit: alert created
            append_audit(
                action="ALERT_CREATED",
                payload={
                    "alert_id": alert_id,
                    "priority": priority,
                    "confidence": state.get("confidence"),
                    "final_outcome": final_outcome,
                },
                uow=uow,
                entity_id=entity_id,
            )

            # 4. Create SAR draft
            sar = create_sar_draft(
                entity_id=entity_id,
                narrative=narrative,
                citations=citations,
                uow=uow,
                alert_id=alert_id,
            )
            uow.session.flush()
            sar_id = sar.id

            # 5. Audit: SAR created
            append_audit(
                action="SAR_DRAFT_CREATED",
                payload={"sar_id": sar_id, "alert_id": alert_id, "version": 1},
                uow=uow,
                entity_id=entity_id,
            )

            # 6. Mark RawEvent processed -- same uow/session as everything above,
            # so this stays part of the one atomic transaction (a second, nested
            # UnitOfWork here opened a second SQLite connection while this one's
            # transaction was still open, deadlocking with "database is locked").
            raw_ev = uow.events.get(state.get("event_id", ""))
            if raw_ev:
                raw_ev.processed = True
                raw_ev.status = "PROCESSED"

            uow.commit()

    except Exception as exc:  # noqa: BLE001
        log.error("reporter: DB write failed for entity=%s: %s", entity_id, exc)
        state["error"] = f"DB write failed: {exc}"
        state["final_outcome"] = final_outcome
        state["trace"] = tb
        return state

    # ── Broker events ─────────────────────────────────────────────────────────
    try:
        broker.publish(ALERT_NEW, {
            "alert_id": alert_id,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "priority": priority,
            "band": risk_band,
            "confidence": state.get("confidence"),
        })
        if sar_id:
            broker.publish(SAR_READY, {
                "sar_id": sar_id,
                "alert_id": alert_id,
                "entity_name": entity_name,
                "priority": priority,
            })
    except Exception as exc:  # noqa: BLE001
        log.warning("reporter: broker publish failed (non-fatal): %s", exc)

    state["alert_id"] = alert_id
    state["sar_id"] = sar_id
    state["final_outcome"] = final_outcome
    state["trace"] = tb
    log.info(
        "reporter: DONE entity=%s alert=%s sar=%s outcome=%s",
        entity_name, alert_id, sar_id, final_outcome,
    )
    return state
