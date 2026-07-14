"""Rapidfuzz name screening: entities/persons vs sanctions_cache, both directions.

Forward: screen_entity_and_persons() checks our entities/directors against
sanctions_cache (the classic screening direction).

Reverse: screen_watchlist_addition() checks a newly-added sanctioned name
(from sanctions_list.py's "watchlist_addition" events) against our existing
entities/directors -- closing the loop sanctions_list.py deferred to "the
pipeline" when it was built.

Not hash-chained: screened_out audit entries use the same UNCHAINED_SPRINT2
sentinel as sanctions_list.py's list_refreshed entries -- see that module
for why (real chaining is Dev 3's Sprint 3).
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from rapidfuzz import fuzz

from app.models.audit import AuditLog
from app.models.entities import Entity, EntityPerson
from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import FeedAdapter

log = logging.getLogger(__name__)

SCREENING_PASS_THRESHOLD = 80.0
UNCHAINED_SENTINEL = "UNCHAINED_SPRINT2"

# Below this length, token_set_ratio's subset-match behavior scores a false
# 100 whenever the short candidate's only token happens to appear anywhere
# in the input (e.g. normalize_name() strips a Cyrillic name down to a
# single surviving digit like "1", which then "subset matches" any name
# ending in "1"). Real names normalize to something longer than this.
MIN_NORMALIZED_NAME_LENGTH = 3

# (display_name, name_normalized, source, list_source_or_none)
_Candidate = tuple[str, str, str, str | None]


@dataclass(frozen=True, slots=True)
class ScreeningMatch:
    candidate_name: str  # the name we searched with
    matched_name: str
    matched_name_normalized: str
    score: float
    source: str  # "sanctions_cache" | "entities" | "entity_persons"
    list_source: str | None  # only meaningful when source == "sanctions_cache"


def fuzzy_match_candidates(
    name: str, candidates: Iterable[_Candidate], threshold: float = SCREENING_PASS_THRESHOLD
) -> list[ScreeningMatch]:
    """Pure matcher: no I/O, easy to unit-test. Candidates already carry their normalized form.

    Skips candidates (and bails out entirely for an input) whose normalized form is shorter
    than MIN_NORMALIZED_NAME_LENGTH. normalize_name() strips to [A-Z0-9 ] only, so
    non-Latin-script names (common in OpenSanctions) can normalize down to nothing or a
    single stray character -- rapidfuzz.token_set_ratio treats a short candidate as fully
    contained in any longer string sharing that token, spuriously scoring 100. See
    MIN_NORMALIZED_NAME_LENGTH's comment for a concrete example this guards against.
    """
    normalized_input = FeedAdapter.normalize_name(name)
    if len(normalized_input) < MIN_NORMALIZED_NAME_LENGTH:
        return []

    matches: list[ScreeningMatch] = []
    for display_name, name_normalized, source, list_source in candidates:
        if len(name_normalized) < MIN_NORMALIZED_NAME_LENGTH:
            continue
        score = fuzz.token_set_ratio(normalized_input, name_normalized)
        if score >= threshold:
            matches.append(
                ScreeningMatch(
                    candidate_name=name,
                    matched_name=display_name,
                    matched_name_normalized=name_normalized,
                    score=float(score),
                    source=source,
                    list_source=list_source,
                )
            )
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches


def _sanctions_candidates() -> list[_Candidate]:
    with UnitOfWork() as uow:
        return [(r.name, r.name_normalized, "sanctions_cache", r.list_source) for r in uow.sanctions.list(active=True)]


def _entity_and_person_candidates() -> list[_Candidate]:
    with UnitOfWork() as uow:
        entity_rows = [(e.name, FeedAdapter.normalize_name(e.name), "entities", None) for e in uow.entities.list()]
        person_rows = [
            (p.person_name, FeedAdapter.normalize_name(p.person_name), "entity_persons", None)
            for p in uow.session.query(EntityPerson).all()
        ]
    return entity_rows + person_rows


def screen_entity_and_persons(
    entity: Entity, persons: list[EntityPerson], candidates: list[_Candidate] | None = None
) -> dict[str, list[ScreeningMatch]]:
    """Forward screening: entity's own name + each linked director's name vs sanctions_cache.

    Returns {name: matches} for names with at least one match >= threshold.
    Names with zero matches get a screened_out audit entry, not an entry in the result dict.
    """
    sanctions_candidates = candidates if candidates is not None else _sanctions_candidates()
    names_to_screen = [entity.name] + [p.person_name for p in persons]

    results: dict[str, list[ScreeningMatch]] = {}
    for name in names_to_screen:
        matches = fuzzy_match_candidates(name, sanctions_candidates)
        if matches:
            results[name] = matches
        else:
            _audit_screened_out(name, context=f"forward_screening:entity={entity.id}")
    return results


def screen_watchlist_addition(payload: dict) -> list[ScreeningMatch]:
    """Reverse screening: a newly-added sanctioned name vs our existing entities/directors.

    `payload` is a sanctions_list.py "watchlist_addition" IngestedEvent.payload dict
    (must contain "sanctioned_name").
    """
    sanctioned_name = payload["sanctioned_name"]
    matches = fuzzy_match_candidates(sanctioned_name, _entity_and_person_candidates())
    if not matches:
        _audit_screened_out(sanctioned_name, context="reverse_screening:watchlist_addition")
    return matches


def _audit_screened_out(name: str, context: str) -> None:
    """Write a screened_out audit_log row. NOT hash-chained -- see module docstring."""
    payload = {"name": name, "context": context, "threshold": SCREENING_PASS_THRESHOLD}
    payload_json = json.dumps(payload, sort_keys=True)
    timestamp = datetime.now(timezone.utc)
    entry_hash = hashlib.sha256(
        f"{UNCHAINED_SENTINEL}|screened_out|{payload_json}|{timestamp.isoformat()}".encode("utf-8")
    ).hexdigest()

    with UnitOfWork() as uow:
        uow.audit_log.add(
            AuditLog(
                actor_id="system",
                action="screened_out",
                payload=payload_json,
                prev_hash=UNCHAINED_SENTINEL,
                entry_hash=entry_hash,
                timestamp=timestamp,
            )
        )
        uow.commit()
    log.debug("screened_out: %r (%s)", name, context)
