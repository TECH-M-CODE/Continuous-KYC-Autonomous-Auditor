import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, func
from app.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String(36), default=lambda: str(uuid.uuid4()), nullable=False)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    payload = Column(Text, nullable=True)  # Store JSON serialization of details
    prev_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), unique=True, nullable=False)
    signature = Column(String(256), nullable=True)
    timestamp = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self):
        return f"<AuditLog seq={self.seq} action={self.action} entry_hash={self.entry_hash}>"
