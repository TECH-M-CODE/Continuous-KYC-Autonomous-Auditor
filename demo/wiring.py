"""Binds the timed engine to the real app stack. The ONLY file importing app
singletons, so the engine and scenarios stay unit-testable.

PipelineInjectAdapter routes through persist_events → run_pipeline — the exact
path legacy run_scenario() uses — so both modes share one pipeline.
"""

from __future__ import annotations

from demo.scenario_engine import Console, PipelineInjectAdapter, ScenarioEngine


async def build_engine(*, console: Console, interactive: bool, rehearsal: bool) -> ScenarioEngine:
    # await_pipeline=True in rehearsal so assertions never race the work they
    # assert on; False in a live demo so the clock does not stall on an LLM call.
    inject = PipelineInjectAdapter(await_pipeline=rehearsal)

    txn_replayer = sanctions = probe = None
    try:
        from app.demo_support import (  # type: ignore
            TxnReplayer, SanctionsAdapter, StateProbe,
        )
        txn_replayer, sanctions, probe = TxnReplayer(), SanctionsAdapter(), StateProbe()
    except ImportError as exc:
        # money_laundering needs the replayer; false_positive does not. Degrade
        # rather than block Dev 2 before app.demo_support lands.
        console.warn(f"app.demo_support unavailable ({exc}) — replay/sanctions steps will fail")

    return ScenarioEngine(
        inject_adapter=inject,
        txn_replayer=txn_replayer,
        sanctions_adapter=sanctions,
        state_probe=probe,
        console=console,
        interactive=interactive,
        rehearsal=rehearsal,
    )


async def verify_scenario(name: str, module) -> list[str]:
    from app.demo_support import (  # type: ignore
        seeded_watchlist, mapped_accounts, watchlist_directors,
    )
    if name == "money_laundering":
        return module.verify(seeded_watchlist(), mapped_accounts())
    if name == "false_positive":
        return module.verify(seeded_watchlist())
    if name == "sanctions_update":
        return module.verify(watchlist_directors())
    return []