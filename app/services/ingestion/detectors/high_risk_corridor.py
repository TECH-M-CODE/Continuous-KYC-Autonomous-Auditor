"""High-risk corridor detector -- STUB, interface only.

Sprint 2 plan explicitly scopes this as interface-plus-TODO alongside
rapid_movement.py: "finish in Sprint 3 per roadmap". Wired into
transactions.py's detector list now so Sprint 3 only has to fill in
scan(), not re-plumb the pipeline.

TODO(Sprint 3): flag cross-border transfers routed through FATF-listed
jurisdictions. Two concrete facts to save re-discovery:
  1. Sender_bank_location / Receiver_bank_location in the SAML-D source are
     label-encoded ints. data/aml_transactions/encoders_samld.pkl is a
     dict[str, list[str]]; encoders["Sender_bank_location"][code] gives the
     country name (18 countries total: Albania, Austria, France, Germany,
     India, Italy, Japan, Mexico, Morocco, Netherlands, Nigeria, Pakistan,
     Spain, Switzerland, Turkey, UAE, UK, USA). transactions.py does not
     currently decode these columns -- that decode needs adding upstream
     before this detector can see country names.
  2. "High-risk jurisdiction" needs a FATF blacklist/greylist, which does
     not exist anywhere in this codebase yet. Dev 1's Sprint 2 task list
     includes extending policy.yaml with `jurisdiction_factors` (FATF
     country -> 1.3, else 1.0) -- this detector should read that list once
     it lands, not maintain its own separate copy.
"""
from __future__ import annotations

from app.services.ingestion.detectors import DetectorHit, TxnRecord

DEFAULT_WINDOW_HOURS = 24.0
DEFAULT_MIN_COUNT = 2


class HighRiskCorridorDetector:
    typology = "high_risk_corridor"

    def __init__(self, window_hours: float = DEFAULT_WINDOW_HOURS, min_count: int = DEFAULT_MIN_COUNT) -> None:
        self._window_hours = window_hours
        self._min_count = min_count

    def scan(self, account_no: str, window_hours: float, transactions: list[TxnRecord]) -> DetectorHit | None:
        # TODO(Sprint 3): implement FATF-corridor detection. See module docstring.
        return None
