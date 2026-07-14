import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class SARDraft(Base):
    __tablename__ = "sar_draft"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_id = Column(String(36), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1, nullable=False)
    narrative = Column(Text, nullable=True)
    citations = Column(Text, nullable=True)  # Store JSON serialization of citations list
    status = Column(String(50), default="DRAFT")
    previous_version_id = Column(String(36), ForeignKey("sar_draft.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    alert = relationship("Alert", back_populates="sar_drafts")
    entity = relationship("Entity", back_populates="sar_drafts")
    previous_version = relationship("SARDraft", remote_side=[id])

    def __repr__(self):
        return f"<SARDraft id={self.id} entity_id={self.entity_id} version={self.version} status={self.status}>"
