"""Shared contract for rule-based transaction typology detectors.

Evidence keys (n, approx_amount, window_hours, txn_ids) are the interface
this package's detectors and Dev 3's explainability narrator both consume
-- defined once here, not duplicated per detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class TxnRecord:
    """One replayed transaction, already resolved to approximate real currency."""

    txn_id: str
    account_no: str
    counterparty_account: str
    amount: float  # inverse-scaled approximate amount, not the raw z-score
    timestamp: datetime  # UTC
    is_cross_border: bool


@dataclass(frozen=True, slots=True)
class DetectorHit:
    typology: str
    account_no: str
    evidence: dict[str, Any]  # {n, approx_amount, window_hours, txn_ids}


class Detector(Protocol):
    typology: str

    def scan(self, account_no: str, window_hours: float, transactions: list[TxnRecord]) -> DetectorHit | None:
        """Inspect `transactions` (already trimmed to `window_hours`) for `account_no`. None if no hit."""
        ...


__all__ = ["TxnRecord", "DetectorHit", "Detector"]
