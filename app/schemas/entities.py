"""Entity DTOs (see docs/api_contract.md #2, docs/canonical_domain_model.md #1/#2/#7)."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

RiskBand = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class PersonDTO(BaseModel):
    id: str
    full_name: str
    role: str  # UBO | DIRECTOR | SHAREHOLDER | SIGNATORY
    is_pep: bool
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    risk_score: float
    risk_band: RiskBand


class RiskEventDTO(BaseModel):
    id: str
    event_category: str  # SANCTION | ADVERSE_MEDIA | PEP_UPDATE | TRANSACTION
    severity: str  # LOW | MEDIUM | HIGH | CRITICAL
    score_delta: float
    reasoning: str
    created_at: datetime


class EntitySummaryDTO(BaseModel):
    id: str
    name: str
    type: str  # COMPANY | PERSON
    risk_score: float
    risk_band: RiskBand


class EntityDetailDTO(EntitySummaryDTO):
    jurisdiction: str
    peps: list[PersonDTO]
    recent_events: list[RiskEventDTO]


class DecisionNodeData(BaseModel):
    label: str
    score_change: Optional[float] = None
    date: datetime


class DecisionNodePosition(BaseModel):
    x: float
    y: float


class DecisionNodeDTO(BaseModel):
    id: str
    type: Literal["news", "match", "policy", "human"]
    data: DecisionNodeData
    position: Optional[DecisionNodePosition] = None


class DecisionEdgeDTO(BaseModel):
    id: str
    source: str
    target: str
    animated: bool
    label: Optional[str] = None


class EntityGraphDTO(BaseModel):
    nodes: list[DecisionNodeDTO]
    edges: list[DecisionEdgeDTO]
