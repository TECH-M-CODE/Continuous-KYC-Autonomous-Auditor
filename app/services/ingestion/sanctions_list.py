"""SanctionsListAdapter: ETag-gated diff refresh of OFAC/OpenSanctions into sanctions_cache.

Sequence 6.3 in the Sprint 2 plan. See this module's class docstring for the
five concrete design decisions (fake file:// ETag, OpenSanctions sampling,
diff key, unchained audit entry, injected cache) flagged at review time.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from app.infrastructure.cache import LocalMemoryCache
from app.models.audit import AuditLog
from app.models.sanctions import SanctionsCache
from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import FeedAdapter, IngestedEvent
from data.prep.gen_directors import EXACT_MATCH_NAMES  # keep the guaranteed-inclusion set in sync

log = logging.getLogger(__name__)

OFAC_PATH = Path("data/sanctions/ofac_sdn_cleaned.csv")
OPENSANCTIONS_PATH = Path("data/sanctions/opensanctions_targets_cleaned.parquet")

OPENSANCTIONS_SCHEMAS = ("Person", "Company")
OPENSANCTIONS_SAMPLE_SIZE = 5_000
RANDOM_SEED = 42

CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # effectively persistent for the demo's lifetime
UNCHAINED_SENTINEL = "UNCHAINED_SPRINT2"  # not "GENESIS" -- real chaining is Dev 3's Sprint 3


@dataclass(frozen=True, slots=True)
class SanctionRecord:
    name: str
    aliases: list[str]
    program: str | None


def _load_ofac_records() -> list[SanctionRecord]:
    df = pd.read_csv(OFAC_PATH, usecols=["name", "program"]).dropna(subset=["name"])
    return [
        SanctionRecord(
            name=str(row.name).strip(),
            aliases=[],
            program=None if pd.isna(row.program) else str(row.program),
        )
        for row in df.itertuples(index=False)
    ]


def _load_opensanctions_records() -> list[SanctionRecord]:
    df = pd.read_parquet(OPENSANCTIONS_PATH, columns=["schema", "name", "aliases"])
    df = df[df["schema"].isin(OPENSANCTIONS_SCHEMAS)].dropna(subset=["name"])

    guaranteed = df[df["name"].isin(EXACT_MATCH_NAMES)]
    remainder = df.drop(guaranteed.index)
    sample_size = min(OPENSANCTIONS_SAMPLE_SIZE, len(remainder))
    sampled = remainder.sample(n=sample_size, random_state=RANDOM_SEED)
    combined = pd.concat([guaranteed, sampled], ignore_index=True)

    records = []
    for row in combined.itertuples(index=False):
        aliases_raw = row.aliases
        aliases = (
            [a.strip() for a in str(aliases_raw).split(",") if a.strip()]
            if aliases_raw is not None and not pd.isna(aliases_raw)
            else []
        )
        records.append(SanctionRecord(name=str(row.name).strip(), aliases=aliases, program=None))
    return records


# list_source -> (path, loader)
_SOURCES: dict[str, tuple[Path, Callable[[], list[SanctionRecord]]]] = {
    "OFAC": (OFAC_PATH, _load_ofac_records),
    "OPENSANCTIONS": (OPENSANCTIONS_PATH, _load_opensanctions_records),
}


class SanctionsListAdapter(FeedAdapter):
    """ETag-gated diff sync of OFAC + OpenSanctions into sanctions_cache.

    See module docstring for the design decisions this class embodies:
    fake file:// ETag, OpenSanctions sampling with guaranteed inclusions,
    name_normalized diff key, and an explicitly unchained audit entry.
    """

    name = "sanctions_list"
    schedule_seconds = 6 * 60 * 60

    def __init__(self, cache: LocalMemoryCache | None = None) -> None:
        self._cache = cache if cache is not None else LocalMemoryCache()

    async def fetch(self) -> list[IngestedEvent]:
        events: list[IngestedEvent] = []
        for list_source, (path, loader) in _SOURCES.items():
            events.extend(self._sync_one_source(list_source, path, loader))
        return events

    def _sync_one_source(
        self, list_source: str, path: Path, loader: Callable[[], list[SanctionRecord]]
    ) -> list[IngestedEvent]:
        if not path.exists():
            log.warning("sanctions_list: source file missing for %s: %s", list_source, path)
            return []

        etag = self._compute_file_etag(path)
        cache_key = f"sanctions:etag:{list_source}"
        cached_etag = self._cache.get(cache_key)
        if cached_etag == etag:
            log.debug("sanctions_list: %s unmodified (etag=%s), skipping", list_source, etag)
            return []

        log.info("sanctions_list: %s changed (etag %s -> %s), syncing", list_source, cached_etag, etag)
        records = loader()
        added, versioned_out = self._diff_and_apply(list_source, records, etag)
        self._audit_list_refreshed(list_source, added_count=len(added), versioned_out_count=versioned_out, etag=etag)

        # Cache commit happens last, only after a fully successful sync --
        # "never write partial data over cache" from the plan.
        self._cache.set(cache_key, etag, ttl_seconds=CACHE_TTL_SECONDS)

        now = datetime.now(timezone.utc)
        return [self._addition_event(list_source, record, now) for record in added]

    def _diff_and_apply(
        self, list_source: str, records: list[SanctionRecord], etag: str
    ) -> tuple[list[SanctionRecord], int]:
        with UnitOfWork() as uow:
            existing_active = {
                row.name_normalized: row
                for row in uow.sanctions.list(active=True)
                if row.list_source == list_source
            }
            source_by_norm = {self.normalize_name(record.name): record for record in records}

            versioned_out = 0
            for name_norm, row in existing_active.items():
                if name_norm not in source_by_norm:
                    row.active = False  # mutating a session-tracked instance; flushed on commit
                    versioned_out += 1

            added: list[SanctionRecord] = []
            version_label = etag[:12]
            for name_norm, record in source_by_norm.items():
                if name_norm in existing_active:
                    continue
                uow.sanctions.add(
                    SanctionsCache(
                        name=record.name,
                        name_normalized=name_norm,
                        aliases=json.dumps(record.aliases),
                        list_source=list_source,
                        sanction_program=record.program,
                        list_version=version_label,
                        active=True,
                    )
                )
                added.append(record)

            uow.commit()

        return added, versioned_out

    def _addition_event(self, list_source: str, record: SanctionRecord, occurred_at: datetime) -> IngestedEvent:
        name_norm = self.normalize_name(record.name)
        return IngestedEvent(
            event_type="watchlist_addition",
            source=f"sanctions_list:{list_source.lower()}",
            title=f"New {list_source} watchlist entry: {record.name}",
            text=f"{record.name} added to the {list_source} sanctions/watchlist feed.",
            occurred_at=occurred_at,
            payload={
                "sanctioned_name": record.name,
                "sanctioned_name_normalized": name_norm,
                "list_source": list_source,
                "program": record.program,
                "aliases": record.aliases,
            },
        )

    @staticmethod
    def _audit_list_refreshed(list_source: str, added_count: int, versioned_out_count: int, etag: str) -> None:
        """Write an audit_log row for this refresh. NOT hash-chained -- see module docstring."""
        payload = {
            "list_source": list_source,
            "added": added_count,
            "versioned_out": versioned_out_count,
            "etag": etag,
        }
        payload_json = json.dumps(payload, sort_keys=True)
        timestamp = datetime.now(timezone.utc)
        entry_hash = hashlib.sha256(
            f"{UNCHAINED_SENTINEL}|list_refreshed|{payload_json}|{timestamp.isoformat()}".encode("utf-8")
        ).hexdigest()

        with UnitOfWork() as uow:
            uow.audit_log.add(
                AuditLog(
                    actor_id="system",
                    action="list_refreshed",
                    payload=payload_json,
                    prev_hash=UNCHAINED_SENTINEL,
                    entry_hash=entry_hash,
                    timestamp=timestamp,
                )
            )
            uow.commit()

    @staticmethod
    def _compute_file_etag(path: Path) -> str:
        """Stand-in for an HTTP ETag header -- see module docstring's file:// shim note."""
        stat = path.stat()
        raw = f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
