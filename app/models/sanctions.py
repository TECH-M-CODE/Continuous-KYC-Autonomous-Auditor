import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, func
from app.models.base import Base

class SanctionsCache(Base):
    __tablename__ = "sanctions_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    name_normalized = Column(String(255), nullable=False, index=True)
    aliases = Column(Text, nullable=True)  # Store JSON serialization or comma-separated names
    list_source = Column(String(100), nullable=True)
    sanction_program = Column(String(255), nullable=True)
    list_version = Column(String(50), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    def __repr__(self):
        return f"<SanctionsCache id={self.id} name={self.name} active={self.active}>"
