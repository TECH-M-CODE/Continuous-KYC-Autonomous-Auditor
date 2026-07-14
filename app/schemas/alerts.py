"""Alert DTOs (see docs/api_contract.md #3, docs/canonical_domain_model.md #8/#9)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

AlertPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
AlertStatus = Literal["OPEN", "IN_PROGRESS", "ESCALATED", "RESOLVED", "DISMISSED"]


class EvidenceItemDTO(BaseModel):
    source: str
    snippet: str
    url: Optional[str] = None
    relevance: float = Field(ge=0.0, le=1.0)


class InvestigationDTO(BaseModel):
    summary: str
    evidence: list[EvidenceItemDTO]


class AlertSummaryDTO(BaseModel):
    id: str
    entity_name: str
    priority: AlertPriority
    status: AlertStatus
    created_at: datetime


class AlertDetailDTO(AlertSummaryDTO):
    investigation: InvestigationDTO


class AlertActionRequest(BaseModel):
    action: Literal["DISMISS", "ESCALATE", "RESOLVE"]
    reasoning: str
