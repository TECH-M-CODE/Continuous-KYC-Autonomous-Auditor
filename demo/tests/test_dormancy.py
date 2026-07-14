"""Dormancy: statistical correctness + the invariant that it NEVER scores."""

from datetime import datetime, timedelta, timezone
import dataclasses
from demo.dormancy import check_dormancy, DormancyFlag, MIN_BASELINE_PER_WEEK


NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _txns(day_offsets):
    return [NOW - timedelta(days=d) for d in day_offsets]


def test_reactivation_flagged():
    baseline = [d for d in range(15, 90, 3)]          # steady ~2.3/wk
    burst = [d for d in range(0, 14)]                 # daily in window
    flag = check_dormancy("acc-1", _txns(baseline + burst), now=NOW)
    assert flag is not None
    assert flag.multiplier >= 3.0
    assert flag.priority == "low"


def test_cold_start_guard_suppresses_new_account():
    # Almost no baseline activity → never "reactivated", just new.
    flag = check_dormancy("acc-2", _txns([0, 1, 2, 3, 4]), now=NOW)
    assert flag is None


def test_steady_account_not_flagged():
    steady = [d for d in range(0, 90, 3)]
    assert check_dormancy("acc-3", _txns(steady), now=NOW) is None


def test_flag_has_no_score_field():
    # The invariant: dormancy is advisory and must be impossible to feed scoring.
    fields = {f.name for f in dataclasses.fields(DormancyFlag)}
    assert "score" not in fields and "band" not in fields