from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from app.models.audit import AuditLog
from app.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)

GENESIS_HASH = "GENESIS"
SYSTEM_ACTOR = "system"


def _normalize_timestamp(timestamp: datetime) -> str:
    """Canonical isoformat string, independent of tz-awareness.

    ``append_audit`` hashes a fresh tz-aware ``datetime.now(timezone.utc)``, but
    SQLite's DateTime column drops tzinfo on round-trip -- a value reloaded via
    ``verify_chain`` comes back naive. Without normalizing, ``.isoformat()``
    produces two different strings for the same instant ("...12+00:00" vs
    "...12"), so recomputing the hash after ANY reload never matches the
    original, for every row, tampered or not.
    """
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    return timestamp.isoformat()


def _compute_entry_hash(
    prev_hash: str,
    seq: int,
    actor: str,
    action: str,
    payload_json: str,
    timestamp: datetime,
) -> str:
    """SHA-256 over the audit chain content."""
    content = (
        f"{prev_hash}|"
        f"{seq}|"
        f"{actor}|"
        f"{action}|"
        f"{payload_json}|"
        f"{_normalize_timestamp(timestamp)}"
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _last_entry(entity_id: str | None, uow: UnitOfWork) -> AuditLog | None:
    """Return the latest audit entry overall.

    The hash chain is one global ledger across every entity, not one chain per
    entity: ``verify_chain(entity_id=None)`` (the ``/audit/verify`` endpoint)
    walks the whole table in global insertion order and expects each entry's
    ``prev_hash`` to equal the *previous row in that order*, regardless of
    which entity it belongs to. Scoping this lookup by ``entity_id`` (as
    before) chains each entity to its own prior entry instead, so as soon as
    two different entities have interleaved audit rows -- true from the first
    real event onward -- the global walk hits a "prev hash mismatch" on
    legitimate, untampered data. ``entity_id`` is accepted for signature
    stability but intentionally unused here.

    Flushes first: SessionLocal is built with autoflush=False (models/base.py),
    and reporter.py calls append_audit() several times per event inside one
    UnitOfWork before its single final commit -- e.g. ENTITY_RISK_UPDATED then
    ALERT_CREATED then SAR_DRAFT_CREATED. Without an explicit flush here, this
    query never sees those still-pending rows from earlier in the same
    request, so every entry in the batch reads back an empty/stale list and
    wrongly computes prev_hash=GENESIS instead of chaining to the one before
    it -- again breaking verification on entirely legitimate data.
    """
    uow.session.flush()
    entries = uow.audit_log.list(entity_id=None)
    return entries[-1] if entries else None


def append_audit(
    action: str,
    payload: dict,
    uow: UnitOfWork,
    *,
    entity_id: str | None = None,
    actor_id: str = SYSTEM_ACTOR,
) -> AuditLog:
    """Append one hash-chained audit entry.

    Must be called inside an open UnitOfWork; the caller is responsible
    for committing the transaction.
    """
    timestamp = datetime.now(timezone.utc)
    payload_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    last_entry = _last_entry(entity_id, uow)

    if last_entry:
        prev_hash = last_entry.entry_hash
        seq = last_entry.seq + 1
    else:
        prev_hash = GENESIS_HASH
        seq = 1

    entry_hash = _compute_entry_hash(
        prev_hash=prev_hash,
        seq=seq,
        actor=actor_id,
        action=action,
        payload_json=payload_json,
        timestamp=timestamp,
    )

    entry = AuditLog(
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        payload=payload_json,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        timestamp=timestamp,
    )

    uow.audit_log.add(entry)

    log.debug(
        "audit: seq=%d action=%s entity=%s hash=%s",
        seq,
        action,
        entity_id,
        entry_hash[:12],
    )

    return entry


def verify_chain(
    entity_id: str | None,
    uow: UnitOfWork,
) -> tuple[bool, str | None]:
    """Verify the audit chain for an entity.

    Returns ``(True, None)`` if valid, otherwise
    ``(False, broken_hash)``.
    """
    entries = uow.audit_log.list(entity_id=entity_id)

    if not entries:
        return True, None

    expected_prev = GENESIS_HASH

    for entry in entries:
        if entry.prev_hash != expected_prev:
            log.error(
                "Audit chain broken at seq=%d (prev hash mismatch)",
                entry.seq,
            )
            return False, entry.entry_hash

        expected_hash = _compute_entry_hash(
            prev_hash=entry.prev_hash,
            seq=entry.seq,
            actor=entry.actor_id,
            action=entry.action,
            payload_json=entry.payload or "",
            timestamp=entry.timestamp,
        )

        if expected_hash != entry.entry_hash:
            log.error(
                "Audit chain broken at seq=%d (hash mismatch)",
                entry.seq,
            )
            return False, entry.entry_hash

        expected_prev = entry.entry_hash

    return True, None


class AuditService:
    """Backward-compatible wrapper."""

    @staticmethod
    def append(
        actor: str,
        action: str,
        detail: dict,
        uow: UnitOfWork,
        entity_id: str = None,
    ) -> AuditLog:
        return append_audit(
            action=action,
            payload=detail,
            uow=uow,
            entity_id=entity_id,
            actor_id=actor,
        )

    @staticmethod
    def verify_chain(
        uow: UnitOfWork,
        entity_id: str | None = None,
    ) -> dict:
        valid, broken = verify_chain(entity_id, uow)
        return {
            "valid": valid,
            "checked": len(uow.audit_log.list(entity_id=entity_id)),
            "first_bad_hash": broken,
        }


__all__ = [
    "append_audit",
    "verify_chain",
    "AuditService",
    "GENESIS_HASH",
]