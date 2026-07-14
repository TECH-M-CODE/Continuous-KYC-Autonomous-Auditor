"""Demo CLI:  python -m demo.run <scenario> [--reset] [--auto] [--verify] [--snapshot]

    --reset     restore the pristine DB before running
    --auto      non-interactive: PAUSE steps become short sleeps (CI / rehearsal)
    --rehearsal enforce ASSERT_STATE guardrails and fail on assertion
    --verify    run scenario pre-flight checks and exit (no injection)
    --snapshot  capture the current DB as the pristine snapshot and exit
    --no-strict-snapshot  allow restoring a schema-mismatched snapshot (escape hatch)

Wiring the real stack lives in `demo/wiring.py` so this file stays about CLI
plumbing. When the app singletons aren't importable (early Sprint 3, before
Hour 2), `build_engine` falls back to the traced_pipeline spine automatically.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from demo.scenario_engine import Console, DbSnapshot, ScenarioEngine
from demo.scenarios import money_laundering, false_positive, sanctions_update

SCENARIOS = {
    "money_laundering": money_laundering,
    "false_positive": false_positive,
    "sanctions_update": sanctions_update,
}

DEFAULT_DB = Path("cxkyc.db")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="demo.run")
    p.add_argument("scenario", nargs="?", choices=list(SCENARIOS), help="scenario to run")
    p.add_argument("--reset", action="store_true", help="restore pristine DB first")
    p.add_argument("--auto", action="store_true", help="non-interactive (short pauses)")
    p.add_argument("--rehearsal", action="store_true", help="enforce state assertions")
    p.add_argument("--verify", action="store_true", help="pre-flight checks only")
    p.add_argument("--snapshot", action="store_true", help="capture pristine snapshot and exit")
    p.add_argument("--no-strict-snapshot", action="store_true", help="allow schema mismatch")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    return p.parse_args(argv)


async def _amain(args: argparse.Namespace) -> int:
    console = Console()
    snapshot = DbSnapshot(args.db)

    if args.snapshot:
        snapshot.capture()
        console.ok(f"pristine snapshot captured from {args.db}")
        return 0

    if not args.scenario:
        console.fail("no scenario given. choices: " + ", ".join(SCENARIOS))
        return 2

    module = SCENARIOS[args.scenario]

    # Pre-flight verification uses the real seed via wiring; degrade gracefully
    # if wiring isn't importable yet.
    try:
        from demo import wiring  # local import — optional before Hour 2
    except Exception as exc:  # noqa: BLE001
        console.warn(f"demo.wiring unavailable ({exc}); running with fallback spine")
        wiring = None

    if args.verify:
        if wiring is None:
            console.fail("cannot verify without demo.wiring")
            return 2
        problems = await wiring.verify_scenario(args.scenario, module)
        if problems:
            for prob in problems:
                console.fail(prob)
            return 1
        console.ok(f"{args.scenario}: pre-flight clean")
        return 0

    if args.reset:
        snapshot.restore(strict=not args.no_strict_snapshot)
        console.ok("DB restored to pristine snapshot")

    if wiring is not None:
        engine = await wiring.build_engine(console=console, interactive=not args.auto,
                                           rehearsal=args.rehearsal)
    else:
        console.fail("demo.wiring required to run scenarios (build the real/fallback stack there)")
        return 2

    result = await engine.run(module.build())
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())