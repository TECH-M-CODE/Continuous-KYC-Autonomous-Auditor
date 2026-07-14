from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

class TraceNode(BaseModel):
    id: str
    kind: Literal["event", "screen", "resolve", "verify", "classify",
                  "score", "propagate", "decision"]
    label: str                 # short: e.g. "Fuzzy match 87"
    detail: str                # full sentence: e.g. "Name 'Acme Hldgs' matched watchlist..."
    values: dict               # machine-readable: {"weight": 12, "severity": 0.8, ...}
    outcome: Optional[Literal["pass", "fail", "branch"]] = None

class TraceEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None # e.g. "confidence 0.93 → proceed"

class DecisionTrace(BaseModel):
    trace_id: str
    event_id: str
    entity_id: Optional[str] = None
    final_outcome: Literal["screened_out", "dismissed", "review_queued",
                           "alert_medium", "alert_high", "alert_critical"]
    counterfactual: Optional[str] = None
    nodes: list[TraceNode]
    edges: list[TraceEdge]
    created_at: datetime