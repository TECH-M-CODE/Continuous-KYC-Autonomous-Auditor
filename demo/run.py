"""Demo CLI.

    python -m demo.run money_laundering --reset       # timed, narrated, pause-gated
    python -m demo.run --legacy sanctions_hit         # legacy batch run_scenario()
    python -m demo.run --snapshot                     # capture pristine DB

Flags:
    --reset               restore pristine DB first
    --auto                non-interactive (PAUSE → short sleep)
    --rehearsal           enforce ASSERT_STATE guardrails
    --verify              pre-flight checks only, no injection
    --legacy              run a legacy batch scenario instead of a timed one
    --no-strict-snapshot  allow restoring a schema-mismatched snapshot
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from demo.scenario_engine import Console, DbSnapshot, run_scenario, _SCENARIO_MAP
from demo.scenarios import false_positive, money_laundering, sanctions_update

TIMED = {
    "money_laundering": money_laundering,
    "false_positive": false_positive,
    "sanctions_update": sanctions_update,
}
LEGACY = sorted(_SCENARIO_MAP)
DEFAULT_DB = Path("cxkyc.db")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="demo.run")
    p.add_argument("scenario", nargs="?",
                   help=f"timed: {', '.join(TIMED)} | legacy (--legacy): {', '.join(LEGACY)}")
    p.add_argument("--legacy", action="store_true", help="run a legacy batch scenario")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--auto", action="store_true")
    p.add_argument("--rehearsal", action="store_true")
    p.add_argument("--verify", action="store_true")
    p.add_argument("--snapshot", action="store_true")
    p.add_argument("--no-strict-snapshot", action="store_true")
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
        console.fail(f"no scenario given. timed: {', '.join(TIMED)} | "
                     f"legacy: {', '.join(LEGACY)}")
        return 2

    if args.reset:
        snapshot.restore(strict=not args.no_strict_snapshot)
        console.ok("DB restored to pristine snapshot")

    # ── legacy path: unchanged behaviour, just reachable from the CLI ────────
    if args.legacy:
        if args.scenario not in _SCENARIO_MAP:
            console.fail(f"unknown legacy scenario {args.scenario!r}. known: {', '.join(LEGACY)}")
            return 2
        summary = await run_scenario(args.scenario)
        print(json.dumps(summary, indent=2, default=str))
        return 0

    if args.scenario not in TIMED:
        console.fail(f"unknown timed scenario {args.scenario!r}. known: {', '.join(TIMED)} "
                     f"(did you mean --legacy {args.scenario}?)")
        return 2

    module = TIMED[args.scenario]
    from demo import wiring

    if args.verify:
        problems = await wiring.verify_scenario(args.scenario, module)
        for prob in problems:
            console.fail(prob)
        if problems:
            return 1
        console.ok(f"{args.scenario}: pre-flight clean")
        return 0

    engine = await wiring.build_engine(console=console, interactive=not args.auto,
                                       rehearsal=args.rehearsal)
    result = await engine.run(module.build())
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return asyncio.run(_amain(parse_args(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    raise SystemExit(main())