"""Loop D — autonomous self-assessment (design doc §3 Loop D, sequences 6.4 & 6.5).

Two low-frequency quality checks the design runs alongside the main ingest/process
loops:

* **Red-team drill** — measures screening robustness against name-evasion variants
  (delegates to `app.services.red_team_drill`).
* **Dormancy sweep** — flags watched entities whose activity has anomalously
  changed, treating absence/shift of signal as a soft signal. Never mutates a
  risk score (advisory only), exactly per the activity diagram.

Both write hash-chained audit entries so the checks are themselves auditable.
`run_loop_d()` is scheduled from the FastAPI lifespan (see app/main.py).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timezone

from app.repositories.unit_of_work import UnitOfWork
from app.services.audit_service import append_audit
from app.services.red_team_drill import run_drill
from demo.dormancy import check_dormancy

log = logging.getLogger(__name__)


def _run_red_team() -> dict:
    report = run_drill()
    with UnitOfWork() as uow:
        append_audit(
            action="red_team_drill",
            payload={
                "caught": report.caught,
                "total": report.total,
                "misses_by_class": report.misses_by_class,
            },
            uow=uow,
        )
        uow.commit()
    log.info("loop_d: red-team drill %d/%d caught", report.caught, report.total)
    return report.misses_by_class


def _run_dormancy_sweep() -> int:
    """Sweep watched entities; use their risk_event timestamps as the activity signal.

    Writes a `dormancy_flagged` audit entry per flag and a `dormancy_sweep`
    summary. Returns the number of flags raised. Never changes a risk score.
    """
    flags = 0
    with UnitOfWork() as uow:
        watched = uow.entities.list(watched=True)
        for entity in watched:
            # SQLite stores naive timestamps; check_dormancy compares against a
            # tz-aware "now", so normalize everything to UTC-aware first.
            timestamps = [
                (re.created_at.replace(tzinfo=timezone.utc) if re.created_at.tzinfo is None else re.created_at)
                for re in uow.risk_events.list(entity_id=entity.id)
            ]
            if not timestamps:
                continue
            flag = check_dormancy(entity.id, timestamps)
            if flag is not None:
                flags += 1
                append_audit(
                    action="dormancy_flagged",
                    payload={
                        "baseline_per_week": flag.baseline_per_week,
                        "window_per_week": flag.window_per_week,
                        "multiplier": flag.multiplier,
                        "reason": flag.reason,
                    },
                    uow=uow,
                    entity_id=entity.id,
                )
        append_audit(action="dormancy_sweep", payload={"watched": len(watched), "flags": flags}, uow=uow)
        uow.commit()
    log.info("loop_d: dormancy sweep raised %d flag(s) over watched entities", flags)
    return flags


async def run_loop_d() -> None:
    """Async entry point scheduled by APScheduler. Offloads the sync work to a thread."""
    try:
        await asyncio.to_thread(_run_red_team)
        await asyncio.to_thread(_run_dormancy_sweep)
    except Exception:  # noqa: BLE001 — a self-assessment failure must never crash the app
        log.exception("loop_d: self-assessment run failed")


__all__ = ["run_loop_d"]
