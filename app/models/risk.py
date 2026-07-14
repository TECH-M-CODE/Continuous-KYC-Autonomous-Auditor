import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    event_id = Column(String(36), ForeignKey("events_raw.id", ondelete="SET NULL"), nullable=True)
    delta = Column(Float, default=0.0, nullable=False)
    weight = Column(Float, default=0.0, nullable=False)
    severity = Column(String(50), nullable=False)
    jurisdiction_factor = Column(Float, default=1.0, nullable=False)
    score_after = Column(Float, default=0.0, nullable=False)
    event_category = Column(String(100), nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    entity = relationship("Entity", back_populates="risk_events")
    source_event = relationship("RawEvent", back_populates="risk_events")
    alerts = relationship("Alert", back_populates="trigger_event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RiskEvent id={self.id} entity_id={self.entity_id} delta={self.delta} severity={self.severity} score_after={self.score_after}>"
