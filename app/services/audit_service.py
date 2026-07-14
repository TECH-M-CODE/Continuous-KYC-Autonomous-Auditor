import hashlib
import json
from datetime import datetime, timezone
from app.models.audit import AuditLog
from app.repositories.unit_of_work import UnitOfWork

class AuditService:
    @staticmethod
    def append(actor: str, action: str, detail: dict, uow: UnitOfWork, entity_id: str = None) -> AuditLog:
        """Appends a new audit log entry securely into the hash chain."""
        # Get the latest audit log to find the prev_hash
        # Note: In a production app, we would use a lock here to prevent race conditions.
        latest_log = uow.session.query(AuditLog).order_by(AuditLog.seq.desc()).first()
        prev_hash = latest_log.entry_hash if latest_log else "0" * 64
        seq = (latest_log.seq + 1) if latest_log else 1

        created_at = datetime.now(timezone.utc)
        
        # Canonical JSON for hashing: no whitespace, sorted keys
        canonical_detail = json.dumps(detail, separators=(',', ':'), sort_keys=True)
        
        # Build the payload to hash
        hash_payload = f"{prev_hash}|{seq}|{actor}|{action}|{canonical_detail}|{created_at.isoformat()}"
        entry_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()

        entry = AuditLog(
            entity_id=entity_id,
            actor_id=actor,
            action=action,
            payload=canonical_detail,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            timestamp=created_at
        )
        uow.audit_log.add(entry)
        return entry

    @staticmethod
    def verify_chain(uow: UnitOfWork) -> dict:
        """Walks the chain and re-hashes every entry to prove no tampering occurred."""
        logs = uow.session.query(AuditLog).order_by(AuditLog.seq.asc()).all()
        expected_prev = "0" * 64
        
        for log in logs:
            if log.prev_hash != expected_prev:
                return {"valid": False, "checked": len(logs), "first_bad_seq": log.seq}
                
            hash_payload = f"{log.prev_hash}|{log.seq}|{log.actor_id}|{log.action}|{log.payload}|{log.timestamp.isoformat()}"
            computed_hash = hashlib.sha256(hash_payload.encode('utf-8')).hexdigest()
            
            if log.entry_hash != computed_hash:
                return {"valid": False, "checked": len(logs), "first_bad_seq": log.seq}
                
            expected_prev = log.entry_hash

        return {"valid": True, "checked": len(logs), "first_bad_seq": None}