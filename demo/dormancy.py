"""Dormancy detector (sequence 6.5). Stretch, self-contained, ~45 min.

Pure statistical check: trailing-90-day baseline vs 14-day window. Raises a
low-priority nudge on a sudden reactivation. NEVER touches the risk score —
this is an advisory signal, not a scoring input, exactly per the activity diagram.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

BASELINE_DAYS = 90
WINDOW_DAYS = 14
#: Cold-start guard: below this baseline rate the account was never active enough
#: for "reactivation" to mean anything. Prevents flagging brand-new accounts.
MIN_BASELINE_PER_WEEK = 2.0
#: A window rate this many times the baseline rate is a reactivation nudge.
REACTIVATION_MULTIPLIER = 3.0


@dataclass(frozen=True, slots=True)
class DormancyFlag:
    account_id: str
    baseline_per_week: float
    window_per_week: float
    multiplier: float
    reason: str
    priority: str = "low"  # advisory only — never escalates a band


def _per_week(count: int, days: int) -> float:
    return (count / days) * 7.0 if days > 0 else 0.0


def check_dormancy(account_id: str, txn_timestamps: Sequence[datetime],
                   *, now: datetime | None = None) -> DormancyFlag | None:
    """Return a nudge if a previously-quiet account suddenly reactivated, else None.

    Deliberately returns a flag object with NO score field — callers must not be
    able to feed this into scoring even by accident.
    """
    now = now or datetime.now(timezone.utc)
    baseline_start = now - timedelta(days=BASELINE_DAYS)
    window_start = now - timedelta(days=WINDOW_DAYS)

    baseline_txns = [t for t in txn_timestamps if baseline_start <= t < window_start]
    window_txns = [t for t in txn_timestamps if window_start <= t <= now]

    baseline_days_observed = BASELINE_DAYS - WINDOW_DAYS
    baseline_rate = _per_week(len(baseline_txns), baseline_days_observed)
    window_rate = _per_week(len(window_txns), WINDOW_DAYS)

    if baseline_rate < MIN_BASELINE_PER_WEEK:
        return None  # cold-start guard — never active enough to "reactivate"
    if baseline_rate == 0:
        return None
    multiplier = window_rate / baseline_rate
    if multiplier < REACTIVATION_MULTIPLIER:
        return None

    return DormancyFlag(
        account_id=account_id,
        baseline_per_week=round(baseline_rate, 2),
        window_per_week=round(window_rate, 2),
        multiplier=round(multiplier, 2),
        reason=(f"Account activity rose {multiplier:.1f}x over its 90-day baseline "
                f"({baseline_rate:.1f}→{window_rate:.1f} txns/week) in the last "
                f"{WINDOW_DAYS} days."))