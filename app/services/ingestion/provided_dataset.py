"""ProvidedDatasetAdapter: idempotent entity bootstrap + day-0 sanctions-exposure events.

The "system started, immediately found existing exposures" demo opener. See
this module's ProvidedDatasetAdapter docstring for the idempotency design.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import FeedAdapter, IngestedEvent

log = logging.getLogger(__name__)

DEFAULT_SCHEDULE_SECONDS = 24 * 60 * 60  # a daily safety-net check is enough for an idempotent bootstrap


class ProvidedDatasetAdapter(FeedAdapter):
    """Ensures entities exist, then surfaces pre-existing sanctions exposure as events.

    Bootstraps via data.seed.seed_entities.seed() ONLY when the entities
    table is empty -- that function does a destructive delete-all-then-
    reinsert, which is safe on a cold start but would erase live risk_score
    updates if re-run mid-demo. Day-0 event emission for already-flagged
    entities is separately idempotent via base.py's content-hash dedup, so
    repeated scheduled runs are always safe regardless of bootstrap state.
    """

    name = "provided_dataset"
    schedule_seconds = DEFAULT_SCHEDULE_SECONDS

    async def fetch(self) -> list[IngestedEvent]:
        self._ensure_entities_seeded()
        return self._day_zero_sanctions_events()

    @staticmethod
    def _ensure_entities_seeded() -> None:
        with UnitOfWork() as uow:
            existing_count = len(uow.entities.list())
        if existing_count > 0:
            log.debug("provided_dataset: %d entities already present, skipping bootstrap", existing_count)
            return

        log.info("provided_dataset: entities table empty, running seed_entities bootstrap")
        from data.seed.seed_entities import seed as seed_entities  # local import: not a hard dependency at module load

        seed_entities()

    @staticmethod
    def _day_zero_sanctions_events() -> list[IngestedEvent]:
        """Entities carrying seed_entities.py's UNDER_INVESTIGATION status (its sanctions_flag=1 proxy)."""
        now = datetime.now(timezone.utc)
        events: list[IngestedEvent] = []
        with UnitOfWork() as uow:
            flagged = [e for e in uow.entities.list() if e.status == "UNDER_INVESTIGATION"]
            for entity in flagged:
                events.append(
                    IngestedEvent(
                        event_type="sanctions_hit",
                        source="provided_dataset",
                        title=f"Existing sanctions exposure: {entity.name}",
                        text=(
                            f"{entity.name} ({entity.jurisdiction or 'unknown jurisdiction'}) carries a "
                            "pre-existing sanctions flag from the onboarding KYC dataset."
                        ),
                        occurred_at=now,
                        payload={
                            "entity_id": entity.id,
                            "jurisdiction": entity.jurisdiction,
                            "sector": entity.sector,
                            "reason": "pre_existing_sanctions_flag",
                        },
                        entity_hint=entity.id,
                    )
                )
        log.info("provided_dataset: %d entities carry a pre-existing sanctions flag", len(events))
        return events
