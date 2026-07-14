import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, CheckConstraint, Text, Float, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class RawEvent(Base):
    __tablename__ = "events_raw"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    content_hash = Column(String(64), unique=True, nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(String(512), nullable=True)
    title = Column(String(255), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    occurred_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String(50), default="PENDING")
    credibility_score = Column(Float, nullable=True)

    # Relationships
    risk_events = relationship("RiskEvent", back_populates="source_event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_events_raw_processed_occurred", "processed", "occurred_at"),
    )

    def __repr__(self):
        return f"<RawEvent id={self.id} status={self.status} processed={self.processed}>"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    trigger_event_id = Column(String(36), ForeignKey("risk_events.id", ondelete="SET NULL"), nullable=True)
    priority = Column(String(50), default="LOW")
    status = Column(String(50), default="OPEN")
    band = Column(String(50), nullable=False)
    assigned_to = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    entity = relationship("Entity", back_populates="alerts")
    trigger_event = relationship("RiskEvent", back_populates="alerts")
    sar_drafts = relationship("SARDraft", back_populates="alert", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "band IN ('low', 'medium', 'high', 'critical', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="chk_alert_band"
        ),
    )

    def __repr__(self):
        return f"<Alert id={self.id} entity_id={self.entity_id} priority={self.priority} status={self.status} band={self.band}>"
