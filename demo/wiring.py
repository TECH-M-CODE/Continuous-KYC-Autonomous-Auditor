"""Binds the scenario engine to the real app stack. This is the ONLY file that
imports app singletons, so scenarios and the engine stay unit-testable.

Until Dev 1's supervisor lands (~Hour 2), build_engine wires the InjectAdapter
to the traced_pipeline spine (Sprint 2), which still works — that's how Dev 2
dry-runs the engine early per the sprint dependency note.
"""

from __future__ import annotations

from demo.scenario_engine import Console, ScenarioEngine


async def build_engine(*, console: Console, interactive: bool, rehearsal: bool) -> ScenarioEngine:
    # Real wiring (fill in against app singletons):
    #   from app.services.ingestion.adapters import InjectAdapter
    #   from app.demo_support import TxnReplayer, SanctionsAdapter, StateProbe
    # Before Hour 2, point InjectAdapter at traced_pipeline instead of supervisor.
    from app.services.ingestion.adapters.inject import InjectAdapter  # type: ignore
    from app.demo_support import (  # type: ignore
        TxnReplayer, SanctionsAdapter, StateProbe,
    )
    return ScenarioEngine(
        inject_adapter=InjectAdapter(),
        txn_replayer=TxnReplayer(),
        sanctions_adapter=SanctionsAdapter(),
        state_probe=StateProbe(),
        console=console,
        interactive=interactive,
        rehearsal=rehearsal,
    )


async def verify_scenario(name: str, module) -> list[str]:
    """Run a scenario's pre-flight against the real seed."""
    from app.demo_support import seeded_watchlist, mapped_accounts, watchlist_directors  # type: ignore
    if name == "money_laundering":
        return module.verify(seeded_watchlist(), mapped_accounts())
    if name == "false_positive":
        return module.verify(seeded_watchlist())
    if name == "sanctions_update":
        return module.verify(watchlist_directors())
    return []