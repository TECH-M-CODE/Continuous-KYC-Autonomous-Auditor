from typing import List
from sqlalchemy.orm import Session
from app.models.audit import AuditLog

class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, audit_log: AuditLog) -> AuditLog:
        # Append-only. Do not update or delete.
        self.session.add(audit_log)
        return audit_log

    def get(self, seq: int) -> AuditLog:
        return self.session.query(AuditLog).filter(AuditLog.seq == seq).first()

    def list(self, entity_id: str = None, action: str = None) -> List[AuditLog]:
        query = self.session.query(AuditLog)
        if entity_id is not None:
            query = query.filter(AuditLog.entity_id == entity_id)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        return query.order_by(AuditLog.seq.asc()).all()
