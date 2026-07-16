import uuid
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class Entity(Base):
    __tablename__ = "entities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(50), default="Organization")  # "Person" | "Organization"
    registration_number = Column(String(100), nullable=True)
    jurisdiction = Column(String(100), nullable=True)
    sector = Column(String(100), nullable=True)
    risk_score = Column(Float, default=0.0)
    risk_band = Column(String(50), default="LOW")
    status = Column(String(50), default="ACTIVE")
    watched = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    risk_events = relationship("RiskEvent", back_populates="entity", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="entity", cascade="all, delete-orphan")
    sar_drafts = relationship("SARDraft", back_populates="entity", cascade="all, delete-orphan")
    persons = relationship("EntityPerson", back_populates="entity", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Entity id={self.id} name={self.name} watched={self.watched}>"

class EntityPerson(Base):
    __tablename__ = "entity_persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    person_name = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    ownership_percentage = Column(Float, nullable=True)

    # Relationships
    entity = relationship("Entity", back_populates="persons")

    __table_args__ = (
        Index("idx_entity_person_role", "entity_id", "person_name", "role"),
    )

    def __repr__(self):
        return f"<EntityPerson entity_id={self.entity_id} name={self.person_name} role={self.role}>"

class AccountEntityMap(Base):
    __tablename__ = "account_entity_map"

    account_no = Column(String(100), primary_key=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)

    def __repr__(self):
        return f"<AccountEntityMap account_no={self.account_no} entity_id={self.entity_id}>"
