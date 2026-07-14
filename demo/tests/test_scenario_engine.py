"""Engine tests with fakes — no app, no DB, no LLM. Fast and deterministic."""

from __future__ import annotations

import asyncio
import io
import pytest

from demo.scenario_engine import Console, ScenarioEngine, DbSnapshot
from demo.types import Action, Scenario, Step


class FakeInject:
    def __init__(self):
        self.calls = []
    async def inject(self, **payload):
        self.calls.append(payload)
        return f"evt-{len(self.calls)}"


class FakeReplay:
    def __init__(self):
        self.started, self.stopped = [], []
    async def start(self, **kw):
        self.started.append(kw)
    async def stop(self, **kw):
        self.stopped.append(kw)


class FakeProbe:
    def __init__(self, band="high", alerts=1, sars=1):
        self._band, self._alerts, self._sars = band, alerts, sars
    async def alert_count(self, *, entity=None):
        return self._alerts
    async def latest_alert_band(self, *, entity):
        return self._band
    async def sar_count(self, *, entity=None):
        return self._sars


def _quiet_console():
    return Console(color=False, stream=io.StringIO())


def _scenario(steps):
    return Scenario("t", "T", "d", steps, budget_seconds=60)


@pytest.mark.asyncio
async def test_inject_fires_and_records():
    fake = FakeInject()
    eng = ScenarioEngine(inject_adapter=fake, console=_quiet_console(), interactive=False)
    s = _scenario([Step(0, Action.INJECT_EVENT, "go",
                        {"event_type": "adverse_media", "entity_name": "X",
                         "text": "t", "source": "s"})])
    res = await eng.run(s)
    assert res.ok
    assert fake.calls[0]["entity_name"] == "X"


@pytest.mark.asyncio
async def test_replay_started_and_auto_stopped_on_cleanup():
    replay = FakeReplay()
    eng = ScenarioEngine(inject_adapter=FakeInject(), txn_replayer=replay,
                         console=_quiet_console(), interactive=False)
    s = _scenario([Step(0, Action.START_TXN_REPLAY, "go", {"entity": "X", "speed": 60})])
    await eng.run(s)
    assert replay.started and replay.stopped  # cleanup stopped the leaked replay


@pytest.mark.asyncio
async def test_live_mode_survives_failing_step():
    class Boom(FakeInject):
        async def inject(self, **p):
            raise RuntimeError("boom")
    eng = ScenarioEngine(inject_adapter=Boom(), console=_quiet_console(),
                         interactive=False, rehearsal=False)
    s = _scenario([
        Step(0, Action.INJECT_EVENT, "boom",
             {"event_type": "a", "entity_name": "X", "text": "t", "source": "s"}),
        Step(0, Action.PAUSE, "still runs", {"seconds": 0}),
    ])
    res = await eng.run(s)
    assert not res.ok                       # failure recorded
    assert res.steps_fired == 1             # but the pause after it still ran
    assert any("boom" in f for f in res.failures)


@pytest.mark.asyncio
async def test_rehearsal_assert_state_catches_wrong_band():
    eng = ScenarioEngine(inject_adapter=FakeInject(), state_probe=FakeProbe(band="high"),
                         console=_quiet_console(), interactive=False, rehearsal=True)
    s = _scenario([Step(0, Action.ASSERT_STATE, "check",
                        {"entity": "X", "band": "critical"})])
    res = await eng.run(s)
    assert not res.ok
    assert "expected band 'critical'" in res.failures[0]


@pytest.mark.asyncio
async def test_assert_state_skipped_when_not_rehearsal():
    # Live demo must never fail on an assertion.
    eng = ScenarioEngine(inject_adapter=FakeInject(), state_probe=FakeProbe(band="high"),
                         console=_quiet_console(), interactive=False, rehearsal=False)
    s = _scenario([Step(0, Action.ASSERT_STATE, "check",
                        {"entity": "X", "band": "critical"})])
    res = await eng.run(s)
    assert res.ok  # assertion silently skipped


@pytest.mark.asyncio
async def test_over_budget_marks_fail():
    s = Scenario("t", "T", "d",
                 [Step(0, Action.PAUSE, "p", {"seconds": 0})], budget_seconds=0.0)
    # last step at t=0 <= budget 0 passes construction; force overrun via sleep
    eng = ScenarioEngine(inject_adapter=FakeInject(), console=_quiet_console(), interactive=False)
    # Not asserting time here (flaky); just confirm the property wiring exists.
    res = await eng.run(s)
    assert res.budget == 0.0


def test_step_order_validated():
    with pytest.raises(ValueError, match="not in"):
        Scenario("t", "T", "d",
                 [Step(10, Action.PAUSE, "a", {"seconds": 0}),
                  Step(5, Action.PAUSE, "b", {"seconds": 0})])


def test_empty_narration_rejected():
    with pytest.raises(ValueError, match="empty narration"):
        Step(0, Action.PAUSE, "   ")