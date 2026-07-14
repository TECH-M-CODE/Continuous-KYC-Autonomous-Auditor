"""Guards the legacy surface. If a refactor breaks POST /api/v1/pipeline/demo,
it breaks here first."""

import inspect
import pytest

from demo import scenario_engine
from demo.scenario_engine import _SCENARIO_MAP, run_scenario


def test_legacy_scenarios_still_registered():
    assert set(_SCENARIO_MAP) == {
        "sanctions_hit", "adverse_media_spike", "transaction_velocity"}


def test_run_scenario_signature_unchanged():
    sig = inspect.signature(run_scenario)
    assert list(sig.parameters) == ["scenario", "entity_id"]
    assert sig.parameters["entity_id"].default is None


def test_run_scenario_still_exported():
    assert "run_scenario" in scenario_engine.__all__
    assert "ScenarioName" in scenario_engine.__all__


@pytest.mark.asyncio
async def test_unknown_legacy_scenario_still_raises_valueerror():
    with pytest.raises(ValueError, match="Unknown scenario"):
        await run_scenario("nope")  # type: ignore[arg-type]


def test_builders_still_produce_events():
    for name, builder in _SCENARIO_MAP.items():
        events = builder("entity-1")
        assert events, f"{name} produced no events"
        assert all(e.entity_hint == "entity-1" for e in events)
        assert all(e.payload.get("entity_name") for e in events)