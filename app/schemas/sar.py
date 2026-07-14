"""SAR DTOs (see docs/api_contract.md #4, docs/canonical_domain_model.md #10)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SARStatus = Literal["DRAFT", "PENDING_APPROVAL", "APPROVED", "REJECTED", "FILED"]


class CitationDTO(BaseModel):
    source: str
    context: str


class SARVersionDTO(BaseModel):
    version: int
    narrative: str
    status: SARStatus
    created_at: datetime


class SARSummaryDTO(BaseModel):
    id: str
    alert_id: str
    entity_name: str
    version: int
    status: SARStatus
    created_at: datetime


class SARDetailDTO(BaseModel):
    id: str
    alert_id: str
    version: int
    status: SARStatus
    narrative: str
    citations: list[CitationDTO]
    previous_versions: list[SARVersionDTO]


class SARUpdateRequest(BaseModel):
    narrative: str
    citations: list[CitationDTO]


class SARDecisionRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    comments: str
