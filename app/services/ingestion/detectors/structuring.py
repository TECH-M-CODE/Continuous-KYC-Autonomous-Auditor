"""Structuring detector: N transactions just under a reporting threshold within a window.

The classic "smurfing" typology -- an account sends several transfers each
just below a reporting threshold (default $10,000) in a short window to
avoid triggering single-transaction scrutiny.
"""
from __future__ import annotations

from app.services.ingestion.detectors import DetectorHit, TxnRecord

DEFAULT_THRESHOLD = 10_000.0
DEFAULT_BAND_LOW_RATIO = 0.80  # "just under" = within [80%, 100%) of the threshold
DEFAULT_MIN_COUNT = 3


class StructuringDetector:
    typology = "structuring"

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        band_low_ratio: float = DEFAULT_BAND_LOW_RATIO,
        min_count: int = DEFAULT_MIN_COUNT,
    ) -> None:
        self._threshold = threshold
        self._band_low = threshold * band_low_ratio
        self._min_count = min_count

    def scan(self, account_no: str, window_hours: float, transactions: list[TxnRecord]) -> DetectorHit | None:
        near_threshold = [t for t in transactions if self._band_low <= t.amount < self._threshold]
        if len(near_threshold) < self._min_count:
            return None

        total_amount = sum(t.amount for t in near_threshold)
        return DetectorHit(
            typology=self.typology,
            account_no=account_no,
            evidence={
                "n": len(near_threshold),
                "approx_amount": round(total_amount, 2),
                "window_hours": window_hours,
                "txn_ids": [t.txn_id for t in near_threshold],
            },
        )
