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
        f"{timestamp.isoformat()}"
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _last_entry(entity_id: str | None, uow: UnitOfWork) -> AuditLog | None:
    """Return the latest audit entry for this entity."""
    entries = uow.audit_log.list(entity_id=entity_id)
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