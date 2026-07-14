"""Hash-chained audit service.

Every compliance decision that the agent network produces must land in the
append-only ``audit_log`` table with a cryptographic hash chain so that any
tampering is immediately detectable.

Chain rule
----------
    entry_hash = SHA-256( prev_hash | action | payload_json | timestamp_iso )

The very first entry for an entity uses ``GENESIS`` as prev_hash.  Subsequent
entries for the same entity chain from the previous entry's ``entry_hash``.

Important: ``append_audit`` must be called *inside* an open ``UnitOfWork``
context, and the UoW must be committed by the caller.  This keeps the audit
write in the same transaction as whatever business object it is recording.
"""

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


def _compute_entry_hash(prev_hash: str, action: str, payload_json: str, timestamp: datetime) -> str:
    """SHA-256 over the four-part chain content."""
    content = f"{prev_hash}|{action}|{payload_json}|{timestamp.isoformat()}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _last_entry_hash(entity_id: str | None, uow: UnitOfWork) -> str:
    """Return the hash of the most recent audit entry for this entity, or GENESIS."""
    entries = uow.audit_log.list(entity_id=entity_id)
    if entries:
        return entries[-1].entry_hash
    return GENESIS_HASH


def append_audit(
    action: str,
    payload: dict,
    uow: UnitOfWork,
    *,
    entity_id: str | None = None,
    actor_id: str = SYSTEM_ACTOR,
) -> AuditLog:
    """Append one hash-chained entry to the audit log.

    Must be called inside an open UoW; the caller is responsible for commit.

    Parameters
    ----------
    action:
        Short verb string, e.g. ``"ALERT_CREATED"``, ``"SAR_DRAFT_CREATED"``,
        ``"ENTITY_RISK_UPDATED"``.
    payload:
        Arbitrary dict. Will be JSON-serialised (sorted keys, str fallback).
    uow:
        Open UnitOfWork — the session must not yet be closed.
    entity_id:
        The entity this entry belongs to. Used to fetch the previous hash.
    actor_id:
        The agent / user that caused this action. Defaults to ``"system"``.
    """
    timestamp = datetime.now(timezone.utc)
    payload_json = json.dumps(payload, sort_keys=True, default=str)
    prev_hash = _last_entry_hash(entity_id, uow)
    entry_hash = _compute_entry_hash(prev_hash, action, payload_json, timestamp)

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
    log.debug("audit: %s entity=%s hash=%.12s", action, entity_id, entry_hash)
    return entry


def verify_chain(entity_id: str | None, uow: UnitOfWork) -> tuple[bool, str | None]:
    """Walk the audit chain for an entity and verify every link.

    Returns ``(True, None)`` if the chain is intact, or
    ``(False, broken_hash)`` identifying the first broken link.
    """
    entries = uow.audit_log.list(entity_id=entity_id)
    if not entries:
        return True, None

    for entry in entries:
        expected = _compute_entry_hash(
            entry.prev_hash, entry.action, entry.payload or "", entry.timestamp
        )
        if expected != entry.entry_hash:
            log.error(
                "Audit chain broken at seq=%d entry_hash=%.12s", entry.seq, entry.entry_hash
            )
            return False, entry.entry_hash

    return True, None


__all__ = ["append_audit", "verify_chain", "GENESIS_HASH"]
