"""Every scenario must build, be time-ordered, and fit its budget. These are the
tests that catch a broken scenario at commit time, not at dress rehearsal."""

import pytest
from demo.scenarios import money_laundering, false_positive, sanctions_update

ALL = [money_laundering, false_positive, sanctions_update]


@pytest.mark.parametrize("mod", ALL, ids=lambda m: m.__name__)
def test_scenario_builds_and_validates(mod):
    s = mod.build()               # __post_init__ enforces order + budget
    assert s.steps
    assert s.steps[-1].at_seconds <= s.budget_seconds


def test_money_laundering_under_4_minutes():
    assert money_laundering.build().budget_seconds <= 240


def test_money_laundering_verify_flags_missing_entity():
    problems = money_laundering.verify(watchlist=[], mapped_accounts={})
    assert len(problems) == 2  # not on watchlist AND no mapped accounts


def test_money_laundering_verify_clean_when_seeded():
    e = money_laundering.WATCHED_ENTITY
    assert money_laundering.verify([e], {e: ["acc-1"]}) == []


def test_false_positive_verify_requires_name_collision():
    assert false_positive.verify(watchlist=[]) != []
    assert false_positive.verify([false_positive.DECOY_NAME]) == []


def test_false_positive_has_no_alert_expectation():
    # The differentiator: the rehearsal assertion expects ZERO alerts.
    s = false_positive.build()
    asserts = [st for st in s.steps if st.action.value == "assert_state"]
    assert asserts and asserts[0].payload["min_alerts"] == 0


def test_sanctions_update_verify_requires_director():
    assert sanctions_update.verify([]) != []
    assert sanctions_update.verify([sanctions_update.WATCHED_DIRECTOR]) == []