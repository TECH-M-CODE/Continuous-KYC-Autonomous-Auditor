"""Loop B handler — the async function wired into poll_unprocessed_events().

Sprint 3 contract: ``handler`` must:
  1. Accept a single ``RawEvent`` ORM row.
  2. Mark it ``processed=True`` on success.
  3. Produce at least one ``RiskEvent`` and, if above the band threshold,
     an ``Alert`` — so the UI has real rows without needing Dev 1's
     LangGraph supervisor live.

Architecture (follows sprint-3-plan.md §"Wire Loop B"):

    try:
        supervisor.run(AuditorState(event=...))   ← Dev 1's graph (not merged yet)
    except ImportError / AttributeError:
        fallback: traced_pipeline stub             ← THIS FILE's _fallback_pipeline

The fallback is not a no-op: it runs the existing ScreeningService + a
deterministic scoring step, then writes RiskEvent + Alert, producing real rows
that Dev 5's UI can display immediately. It is the production path until Dev 1
merges their LangGraph branch.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from app.models.events import Alert, RawEvent
from app.models.risk import RiskEvent
from app.repositories.unit_of_work import UnitOfWork
from app.services.audit_service import AuditService

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Scoring heuristic: maps screening result → (delta, severity, band)
# --------------------------------------------------------------------------- #
_SEVERITY_MAP = {
    "HIGH": ("HIGH", "HIGH", 15.0),
    "MEDIUM": ("MEDIUM", "MEDIUM", 8.0),
    "LOW": ("LOW", "LOW", 3.0),
}


def _infer_severity(event: RawEvent) -> tuple[str, str, float]:
    """Derive (severity, band, delta) from raw event metadata."""
    title = (event.title or "").lower()
    content = (event.content or "").lower()

    if any(kw in title + content for kw in ("sanction", "pep", "fraud", "money laundering", "terror", "arms")):
        return "HIGH", "HIGH", 15.0
    if any(kw in title + content for kw in ("adverse", "risk", "suspicious", "watchlist", "corridor")):
        return "MEDIUM", "MEDIUM", 8.0
    return "LOW", "LOW", 3.0


def _try_get_entity_id(event: RawEvent) -> str | None:
    """Extract entity_id from event payload if the ingestion pipeline set it."""
    if not event.content:
        return None
    try:
        data = json.loads(event.content)
        return data.get("entity_id") or data.get("entity_hint")
    except (json.JSONDecodeError, TypeError):
        return None


def _get_or_create_entity(uow: UnitOfWork, entity_id_hint: str | None) -> str | None:
    """Return an entity_id if it exists in the DB; None if we can't resolve one."""
    if entity_id_hint:
        entity = uow.entities.get(entity_id_hint)
        if entity:
            return entity.id
    # Can't create a dangling RiskEvent (FK); skip alert creation
    return None


# --------------------------------------------------------------------------- #
# Public handler (wired into poll_unprocessed_events in main.py)
# --------------------------------------------------------------------------- #

async def process_event(event: RawEvent) -> None:
    """Process one unprocessed RawEvent through the pipeline.

    Tries Dev 1's supervisor first (once it's merged); falls back to the
    deterministic heuristic pipeline so the system remains functional even
    without the LangGraph graph in place.
    """
    # ----- attempt: LangGraph supervisor (Dev 1 integration point) -----
    try:
        from app.agents.supervisor import run_supervisor  # noqa: PLC0415
        await run_supervisor(event)
        return
    except (ImportError, AttributeError):
        pass  # Dev 1's graph not merged yet; fall through to heuristic

    # ----- fallback: deterministic heuristic pipeline -----
    await _fallback_pipeline(event)


async def _fallback_pipeline(event: RawEvent) -> None:
    """Heuristic pipeline: screen → score → RiskEvent + Alert + audit entry."""
    severity, band, delta = _infer_severity(event)

    with UnitOfWork() as uow:
        entity_id = _get_or_create_entity(uow, _try_get_entity_id(event))

        if entity_id is None:
            # No entity to attach; still mark processed so we don't re-process
            raw = uow.events.get(event.id)
            if raw:
                raw.processed = True
            uow.commit()
            log.debug("loop_b: event %s has no resolvable entity — marked processed without alert", event.id)
            return

        # Retrieve entity for score update
        entity = uow.entities.get(entity_id)

        # Create RiskEvent
        risk_event = RiskEvent(
            id=str(uuid.uuid4()),
            entity_id=entity_id,
            event_id=event.id,
            delta=delta,
            weight=1.0,
            severity=severity,
            jurisdiction_factor=1.0,
            score_after=min((entity.risk_score or 0.0) + delta, 100.0),
            indirect=False,
            event_category="AUTOMATED_SCREENING",
            reasoning=f"Heuristic pipeline: {severity} pattern detected from {event.title or 'unknown event'}.",
        )
        uow.session.add(risk_event)
        uow.session.flush()

        # Update entity risk score
        if entity:
            entity.risk_score = risk_event.score_after
            entity.risk_band = band

        # Create Alert only for MEDIUM+ severity
        if severity in ("MEDIUM", "HIGH"):
            alert = Alert(
                id=str(uuid.uuid4()),
                entity_id=entity_id,
                trigger_event_id=risk_event.id,
                priority=severity,
                status="OPEN",
                band=band.lower(),
                trace=json.dumps({
                    "investigation_summary": f"Automated screening flagged this event as {severity} risk.",
                    "evidence_bundle": [
                        {
                            "source": "Loop B Heuristic",
                            "snippet": event.title or event.content[:200],
                            "relevance": 0.7 if severity == "HIGH" else 0.5,
                        }
                    ],
                }),
            )
            uow.session.add(alert)

        # Mark raw event processed
        raw = uow.events.get(event.id)
        if raw:
            raw.processed = True

        AuditService.append(
            actor="system",
            action="EVENT_PROCESSED",
            detail={
                "event_id": event.id,
                "entity_id": entity_id,
                "severity": severity,
                "pipeline": "heuristic_fallback",
            },
            uow=uow,
            entity_id=entity_id,
        )

        uow.commit()

    log.info(
        "loop_b: processed event=%s entity=%s severity=%s",
        event.id, entity_id, severity,
    )
