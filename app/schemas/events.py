"""SSE event DTOs (see docs/api_contract.md #7, docs/engineering_contract.md #7).

The two docs list slightly different event names; SSEEventType is the union of both
so producers/consumers on either contract are covered.
"""
from typing import Literal

from pydantic import BaseModel

SSEEventType = Literal["alert.new", "alert.updated", "risk.updated", "scenario.progress", "sar.ready"]


class SSEEvent(BaseModel):
    event: SSEEventType
    data: dict
