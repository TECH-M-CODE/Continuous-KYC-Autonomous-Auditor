"""Demo scenario engine.

Injects synthetic events and runs the full agent pipeline for demo/testing
purposes. Three built-in scenarios:

- ``sanctions_hit``        — entity matches OFAC SDN list, high severity
- ``adverse_media_spike``  — burst of adverse news articles, velocity spike
- ``transaction_velocity`` — structuring-pattern transaction anomaly

Usage (programmatic):
    from demo.scenario_engine import run_scenario
    await run_scenario("sanctions_hit")

Usage (HTTP):
    POST /api/v1/pipeline/demo  {"scenario": "sanctions_hit"}
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

from app.models.events import RawEvent
from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import IngestedEvent, persist_events

log = logging.getLogger(__name__)

ScenarioName = Literal["sanctions_hit", "adverse_media_spike", "transaction_velocity"]

# ── Scenario definitions ─────────────────────────────────────────────────────

def _get_first_entity_id() -> str | None:
    """Grab the first entity in the DB to use as a realistic target."""
    with UnitOfWork() as uow:
        entities = uow.entities.list()
        return entities[0].id if entities else None


def _make_sanctions_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="sanctions_hit",
            source="ofac_sdn",
            title="OFAC SDN Match: Viktor Petrov",
            text=(
                "The Office of Foreign Assets Control (OFAC) has added Viktor Petrov, "
                "a director of Acme Import Export Ltd, to the Specially Designated "
                "Nationals (SDN) list effective immediately. The designation is related "
                "to procurement fraud and illicit financing activities in FATF-listed "
                "jurisdictions. All US persons are prohibited from transacting with "
                "this individual and associated entities."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 1.0},
            source_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id=99999",
            entity_hint=entity_id,
        )
    ]


def _make_adverse_media_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="adverse_media_fraud",
            source="reuters",
            title="Investigation: Shell company network linked to money laundering",
            text=(
                "A Reuters investigation has uncovered a network of shell companies "
                "connected to Acme Import Export Ltd. According to sources familiar "
                "with the matter, the network was used to funnel proceeds from "
                "procurement fraud through multiple FATF-listed jurisdictions. "
                "The company's director Viktor Petrov is named as a person of "
                "interest in an ongoing criminal investigation."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 0.85},
            source_url="https://reuters.com/investigation/shell-company-network",
            entity_hint=entity_id,
        ),
        IngestedEvent(
            event_type="adverse_media",
            source="financial_times",
            title="Regulatory scrutiny intensifies for cross-border trade entities",
            text=(
                "Multiple regulatory bodies across the EU and UK are intensifying "
                "scrutiny of cross-border trade entities following the emergence of "
                "the Petrov network revelations. Compliance officers are urged to "
                "review correspondent relationships with entities operating in "
                "higher-risk jurisdictions."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 0.6},
            entity_hint=entity_id,
        ),
    ]


def _make_transaction_velocity_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="transaction_anomaly",
            source="internal_transaction_monitor",
            title="Transaction velocity anomaly: 3x baseline within 24h",
            text=(
                "The internal transaction monitoring system has flagged Acme Import Export Ltd "
                "for a velocity spike: 12 cross-border wire transfers totalling approximately "
                "USD 3.2M were processed in a 24-hour window, representing 3.1x the entity's "
                "established 90-day baseline. The counterparties include entities in jurisdictions "
                "with elevated FATF risk ratings. A structuring pattern cannot be ruled out pending "
                "further review."
            ),
            occurred_at=now,
            payload={
                "entity_name": "Acme Import Export Ltd",
                "severity": 0.8,
                "transaction_count": 12,
                "total_amount_usd": 3_200_000,
                "window_hours": 24,
                "velocity_multiplier": 3.1,
            },
            entity_hint=entity_id,
        )
    ]


_SCENARIO_MAP = {
    "sanctions_hit": _make_sanctions_events,
    "adverse_media_spike": _make_adverse_media_events,
    "transaction_velocity": _make_transaction_velocity_events,
}

# ── Runner ────────────────────────────────────────────────────────────────────

async def run_scenario(scenario: ScenarioName, entity_id: str | None = None) -> dict:
    """Inject scenario events and run the full pipeline. Returns a summary dict.

    Parameters
    ----------
    scenario:
        One of ``"sanctions_hit"``, ``"adverse_media_spike"``, ``"transaction_velocity"``.
    entity_id:
        Override target entity. Defaults to the first entity in the DB.
    """
    from app.agents.supervisor import run_pipeline

    if scenario not in _SCENARIO_MAP:
        raise ValueError(f"Unknown scenario {scenario!r}. Known: {sorted(_SCENARIO_MAP)}")

    target_entity_id = entity_id or _get_first_entity_id()
    log.info("scenario_engine: running '%s' against entity=%s", scenario, target_entity_id)

    # 1. Inject events
    events = _SCENARIO_MAP[scenario](target_entity_id)
    new_count = persist_events(events)
    log.info("scenario_engine: persisted %d new event(s)", new_count)

    # 2. Fetch the just-persisted events (they are PENDING / unprocessed)
    results = []
    with UnitOfWork() as uow:
        pending = uow.events.get_unprocessed(limit=len(events) + 5)
        scenario_events = pending[: len(events)]

    for raw_event in scenario_events:
        state = await run_pipeline(raw_event)
        results.append({
            "event_id": raw_event.id,
            "final_outcome": state.get("final_outcome"),
            "alert_id": state.get("alert_id"),
            "sar_id": state.get("sar_id"),
            "confidence": state.get("confidence"),
            "risk_band": state.get("risk_band"),
            "error": state.get("error"),
        })

    return {
        "scenario": scenario,
        "entity_id": target_entity_id,
        "events_injected": len(events),
        "results": results,
    }


__all__ = ["run_scenario", "ScenarioName"]
