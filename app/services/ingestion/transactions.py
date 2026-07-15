"""TransactionReplayAdapter: replays txn_sample.parquet on a simulated clock.

Default: 1 simulated day = 30 real seconds (configurable). Each fetch() tick
advances a virtual clock proportional to real elapsed time, releases the
transactions that fall in the newly-covered window, updates a rolling
per-account history, and runs every registered detector against accounts
touched this tick. See this module's class docstring for the concrete
design decisions (amount de-scaling, synthetic txn_id, sender-side-only
scope, simulated-time occurred_at, wraparound) flagged at review time.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.entities import AccountEntityMap
from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import FeedAdapter, IngestedEvent
from app.services.ingestion.detectors import Detector, DetectorHit, TxnRecord
from app.services.ingestion.detectors.high_risk_corridor import HighRiskCorridorDetector
from app.services.ingestion.detectors.rapid_movement import RapidMovementDetector
from app.services.ingestion.detectors.structuring import StructuringDetector

log = logging.getLogger(__name__)

TXN_SAMPLE_PATH = Path("data/processed/txn_sample.parquet")

# Extracted once from data/aml_transactions/scaler_samld.pkl's fitted
# StandardScaler (mean_, scale_ for the "Amount" feature) -- hardcoded so
# this adapter doesn't need scikit-learn at runtime for a two-constant
# affine transform. The source Amount column is z-scored; this recovers an
# approximate real-currency value (verified: median ~$6,050, no negatives).
AMOUNT_SCALER_MEAN = 8762.9676
AMOUNT_SCALER_SCALE = 25614.9517

DEFAULT_SCHEDULE_SECONDS = 5
DEFAULT_SECONDS_PER_SIMULATED_DAY = 30.0
DEFAULT_HISTORY_WINDOW_HOURS = 24.0  # covers StructuringDetector's default window


class TransactionReplayAdapter(FeedAdapter):
    """Replays sampled SAML-D transactions on a simulated clock and runs detectors.

    See module docstring for design decisions: amount de-scaling, synthetic
    txn_id, sender-side-only detection scope, simulated-time occurred_at,
    and clock wraparound at the end of the 320-day dataset.
    """

    name = "transactions"
    schedule_seconds = DEFAULT_SCHEDULE_SECONDS

    def __init__(
        self,
        seconds_per_simulated_day: float = DEFAULT_SECONDS_PER_SIMULATED_DAY,
        history_window_hours: float = DEFAULT_HISTORY_WINDOW_HOURS,
        detectors: list[Detector] | None = None,
        source_path: Path = TXN_SAMPLE_PATH,
    ) -> None:
        self._disabled = False

        if not source_path.exists():
            log.warning(
                "TransactionReplayAdapter: %s not found — adapter disabled. "
                "Run data/prep/prep_transactions.py to enable transaction replay.",
                source_path,
            )
            self._disabled = True
            return

        self._seconds_per_simulated_day = seconds_per_simulated_day
        self._history_window_hours = history_window_hours
        self._detectors: list[Detector] = (
            detectors if detectors is not None else [StructuringDetector(), RapidMovementDetector(), HighRiskCorridorDetector()]
        )

        df = (
            pd.read_parquet(source_path, columns=["Sender_account", "Receiver_account", "Amount", "Datetime", "is_cross_border"])
            .sort_values("Datetime")
            .reset_index(drop=True)
        )
        df["txn_id"] = [f"TXN-{i}" for i in df.index]
        df["approx_amount"] = df["Amount"] * AMOUNT_SCALER_SCALE + AMOUNT_SCALER_MEAN
        df["Sender_account"] = df["Sender_account"].astype(str)
        df["Receiver_account"] = df["Receiver_account"].astype(str)

        self._df = df
        self._timestamps = df["Datetime"].to_numpy()
        self._dataset_start: datetime = df["Datetime"].iloc[0].to_pydatetime()
        self._dataset_end: datetime = df["Datetime"].iloc[-1].to_pydatetime()

        self._virtual_clock = self._dataset_start
        self._real_anchor = time.monotonic()
        self._account_history: dict[str, list[TxnRecord]] = {}

        log.info(
            "transactions: loaded %d rows spanning %s -> %s (%.0fs real = 1 simulated day)",
            len(df), self._dataset_start, self._dataset_end, self._seconds_per_simulated_day,
        )

    async def fetch(self) -> list[IngestedEvent]:
        if self._disabled:
            return []  # parquet not ready yet — silently skip

        window_start = self._virtual_clock
        window_end = self._advance_virtual_clock()
        self._virtual_clock = window_end

        window_df = self._slice_window(window_start, window_end)
        if window_df.empty:
            return []

        self._update_history(window_df)
        return self._run_detectors(window_df)

    # -- clock ---------------------------------------------------------------

    def _advance_virtual_clock(self) -> datetime:
        now = time.monotonic()
        elapsed_real = now - self._real_anchor
        self._real_anchor = now
        elapsed_simulated_seconds = elapsed_real * (86400.0 / self._seconds_per_simulated_day)
        candidate = self._virtual_clock + timedelta(seconds=elapsed_simulated_seconds)

        if candidate > self._dataset_end:
            log.info("transactions: reached end of %s dataset, wrapping replay clock to start", self._dataset_end)
            self._account_history.clear()
            return self._dataset_start
        return candidate

    def _slice_window(self, start: datetime, end: datetime) -> pd.DataFrame:
        start_idx = int(np.searchsorted(self._timestamps, np.datetime64(start), side="right"))
        end_idx = int(np.searchsorted(self._timestamps, np.datetime64(end), side="right"))
        return self._df.iloc[start_idx:end_idx]

    # -- history + detection ---------------------------------------------------

    def _update_history(self, window_df: pd.DataFrame) -> None:
        touched_accounts: set[str] = set()
        for row in window_df.itertuples(index=False):
            record = TxnRecord(
                txn_id=row.txn_id,
                account_no=row.Sender_account,
                counterparty_account=row.Receiver_account,
                amount=float(row.approx_amount),
                timestamp=FeedAdapter.coerce_utc(row.Datetime.to_pydatetime()),
                is_cross_border=bool(row.is_cross_border),
            )
            self._account_history.setdefault(record.account_no, []).append(record)
            touched_accounts.add(record.account_no)

        horizon = window_df["Datetime"].max().to_pydatetime() - timedelta(hours=self._history_window_hours)
        for account_no in touched_accounts:
            history = self._account_history[account_no]
            self._account_history[account_no] = [t for t in history if t.timestamp.replace(tzinfo=None) >= horizon]

    def _run_detectors(self, window_df: pd.DataFrame) -> list[IngestedEvent]:
        touched_accounts = {row.Sender_account for row in window_df.itertuples(index=False)}
        events: list[IngestedEvent] = []

        for account_no in touched_accounts:
            history = self._account_history.get(account_no, [])
            for detector in self._detectors:
                hit = detector.scan(account_no, self._history_window_hours, history)
                if hit is not None:
                    events.append(self._hit_to_event(hit))
        return events

    def _hit_to_event(self, hit: DetectorHit) -> IngestedEvent:
        history = self._account_history.get(hit.account_no, [])
        contributing_ids = set(hit.evidence.get("txn_ids", []))
        contributing = [t for t in history if t.txn_id in contributing_ids]
        occurred_at = max((t.timestamp for t in contributing), default=datetime.now(timezone.utc))
        txn_id_preview = ", ".join(list(contributing_ids)[:5])

        return IngestedEvent(
            event_type="transaction_anomaly",
            source="transactions",
            title=f"{hit.typology} pattern on account {hit.account_no}",
            text=(
                f"Account {hit.account_no} shows a {hit.typology} pattern: "
                f"{hit.evidence.get('n')} transactions totaling ~{hit.evidence.get('approx_amount'):.2f} "
                f"within {hit.evidence.get('window_hours')}h. Transactions: {txn_id_preview}"
            ),
            occurred_at=occurred_at,
            payload={"typology": hit.typology, "evidence": hit.evidence},
            entity_hint=self._resolve_entity(hit.account_no),
        )

    @staticmethod
    def _resolve_entity(account_no: str) -> str | None:
        with UnitOfWork() as uow:
            mapping = uow.session.query(AccountEntityMap).filter(AccountEntityMap.account_no == account_no).first()
        return mapping.entity_id if mapping else None
