"""Audit DTOs (see docs/api_contract.md #5, docs/canonical_domain_model.md #11)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditEntryDTO(BaseModel):
    id: str
    entity_id: Optional[str] = None
    actor_id: str
    action: str
    payload: dict
    previous_hash: str
    entry_hash: str
    signature: Optional[str] = None
    timestamp: datetime


class AuditVerifyDTO(BaseModel):
    is_valid: bool
    broken_at_hash: Optional[str] = None
