"""Startup backfill: turn already-high-risk entities into alerts automatically.

The system is meant to behave like an autonomous monitoring agent, so any entity
that is already HIGH or CRITICAL in the watchlist but has no open alert should be
picked up and pushed through the pipeline on its own — producing an alert + SAR
without a human having to click "Inject". This runs once, shortly after startup,
staggered so it doesn't stampede the LLM.
"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)

_BACKFILL_BANDS = {"HIGH", "CRITICAL"}
_ACTIVE_ALERT_STATUSES = {"OPEN", "ESCALATED", "IN_PROGRESS"}


async def backfill_high_risk_alerts(*, initial_delay_seconds: int = 15, stagger_seconds: float = 1.5) -> None:
    """Inject a synthetic monitoring event for each un-alerted HIGH/CRITICAL entity.

    Each injected event flows through the normal Loop B → agent pipeline, so the
    resulting alert/SAR/audit are produced exactly as a manual inject would.
    """
    await asyncio.sleep(initial_delay_seconds)

    from app.repositories.unit_of_work import UnitOfWork
    from app.api.admin import inject_adapter

    try:
        with UnitOfWork() as uow:
            entities = uow.entities.list()
            active_alert_entity_ids = {
                a.entity_id for a in uow.alerts.list()
                if (a.status or "").upper() in _ACTIVE_ALERT_STATUSES
            }
            targets = [
                (e.id, e.name, (e.risk_band or "").upper())
                for e in entities
                if (e.risk_band or "").upper() in _BACKFILL_BANDS
                and e.id not in active_alert_entity_ids
            ]
    except Exception as exc:  # noqa: BLE001
        log.warning("backfill: could not query entities: %s", exc)
        return

    if not targets:
        log.info("backfill: no un-alerted HIGH/CRITICAL entities to process")
        return

    log.info("backfill: auto-generating alerts for %d high-risk entit(y/ies)", len(targets))

    for entity_id, name, band in targets:
        if band == "CRITICAL":
            event_type = "sanctions_hit"
            text = (
                f"Continuous monitoring flagged {name}: sanctions/watchlist exposure with "
                f"severe risk indicators (money laundering / terrorist financing)."
            )
        else:  # HIGH
            event_type = "adverse_media"
            text = (
                f"Continuous monitoring flagged {name}: adverse media linking the entity to "
                f"fraud and money-laundering investigations."
            )
        try:
            inject_adapter.inject_now(
                event_type=event_type,
                title=f"Automated review: {name}",
                text=text,
                entity_hint=entity_id,
                payload={"auto_backfill": True},
            )
            log.info("backfill: queued %s (%s) as %s", name, band, event_type)
        except Exception as exc:  # noqa: BLE001
            log.warning("backfill: failed to queue %s: %s", name, exc)
        await asyncio.sleep(stagger_seconds)
