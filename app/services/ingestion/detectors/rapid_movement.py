"""Rapid movement detector -- STUB, interface only.

Sprint 2 plan explicitly scopes this as interface-plus-TODO: "stub
rapid_movement.py ... with interfaces + TODO (finish in Sprint 3 per
roadmap)". Wired into transactions.py's detector list now so Sprint 3 only
has to fill in scan(), not re-plumb the pipeline.

TODO(Sprint 3): detect "flow-through" accounts -- funds arriving and then
leaving the same account within a short window (e.g. >80% of inbound value
re-sent out within a few hours). Needs both inbound and outbound legs per
account, unlike StructuringDetector which only looks at one direction, so
transactions.py's per-account history will need to track counterparty
direction before this can be finished.
"""
from __future__ import annotations

from app.services.ingestion.detectors import DetectorHit, TxnRecord

DEFAULT_WINDOW_HOURS = 6.0
DEFAULT_MIN_FLOW_THROUGH_RATIO = 0.80


class RapidMovementDetector:
    typology = "rapid_movement"

    def __init__(
        self,
        window_hours: float = DEFAULT_WINDOW_HOURS,
        min_flow_through_ratio: float = DEFAULT_MIN_FLOW_THROUGH_RATIO,
    ) -> None:
        self._window_hours = window_hours
        self._min_flow_through_ratio = min_flow_through_ratio

    def scan(self, account_no: str, window_hours: float, transactions: list[TxnRecord]) -> DetectorHit | None:
        # TODO(Sprint 3): implement flow-through detection. See module docstring.
        return None
