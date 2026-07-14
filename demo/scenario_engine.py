"""Scenario engine — scripted, timed, repeatable event injection.

Design notes:

* Monotonic clock, absolute schedule. Each step sleeps until its absolute
  offset from t0. Sleeping the delta between beats accumulates drift (LLM
  latency inside a step pushes every later beat back); anchoring to t0 does not.
  If a step overruns we warn and fire the next beat immediately rather than
  silently stretching a 4-minute demo into 6.
* Pause steps are wall-clock-free: paused time is subtracted from the schedule
  so a long ad-lib does not make every later beat fire at once.
* Snapshot/restore is a file copy stamped with a schema fingerprint; restoring
  a snapshot whose schema no longer matches is refused.
* Everything is injected — tests pass fakes, run.py passes the real stack.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from demo.types import Action, Scenario, Step

log = logging.getLogger("demo.engine")


class InjectAdapter(Protocol):
    async def inject(
        self,
        *,
        event_type: str,
        entity_name: str,
        text: str,
        source: str,
        is_drill: bool = False,
        **extra: Any,
    ) -> str: ...


class TxnReplayer(Protocol):
    async def start(self, *, entity: str, speed: float, **kw: Any) -> None: ...
    async def stop(self, *, entity: str | None = None) -> None: ...


class SanctionsAdapter(Protocol):
    async def refresh(self, *, planted_addition: dict[str, Any] | None = None) -> None: ...


class StateProbe(Protocol):
    async def alert_count(self, *, entity: str | None = None) -> int: ...
    async def latest_alert_band(self, *, entity: str) -> str | None: ...
    async def sar_count(self, *, entity: str | None = None) -> int: ...


class Console:
    """Narration surface. The co-presenter reads this; keep it clean."""

    DIM, BOLD = "\033[2m", "\033[1m"
    CYAN, GREEN, YELLOW, RED, RESET = "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"

    def __init__(self, *, color: bool = True, stream=sys.stdout) -> None:
        self._color = color and stream.isatty()
        self._stream = stream

    def _c(self, code: str, text: str) -> str:
        return f"{code}{text}{self.RESET}" if self._color else text

    def _emit(self, line: str = "") -> None:
        print(line, file=self._stream, flush=True)

    def banner(self, scenario: Scenario) -> None:
        self._emit()
        self._emit(self._c(self.BOLD, "═" * 72))
        self._emit(self._c(self.BOLD, f"  {scenario.title}"))
        self._emit(self._c(self.DIM, f"  {scenario.description}"))
        self._emit(self._c(self.DIM,
                   f"  budget: {scenario.budget_seconds:.0f}s   steps: {len(scenario.steps)}"))
        self._emit(self._c(self.BOLD, "═" * 72))
        self._emit()

    def narrate(self, elapsed: float, step: Step) -> None:
        stamp = self._c(self.DIM, f"[t+{elapsed:6.1f}s]")
        cue = self._c(self.CYAN + self.BOLD, step.narration)
        self._emit(f"{stamp}  {cue}")
        self._emit(self._c(self.DIM, f"            └─ {step.action.value}  {_compact(step.payload)}"))

    def pause_prompt(self, message: str) -> None:
        self._emit()
        self._emit(self._c(self.YELLOW + self.BOLD, f"  ⏸  {message}"))
        self._emit(self._c(self.DIM, "     press ENTER to continue…"))

    def ok(self, msg: str) -> None:
        self._emit(self._c(self.GREEN, f"  ✔ {msg}"))

    def warn(self, msg: str) -> None:
        self._emit(self._c(self.YELLOW, f"  ⚠ {msg}"))

    def fail(self, msg: str) -> None:
        self._emit(self._c(self.RED + self.BOLD, f"  ✘ {msg}"))

    def summary(self, result: "RunResult") -> None:
        self._emit()
        self._emit(self._c(self.BOLD, "─" * 72))
        status = (self._c(self.GREEN + self.BOLD, "PASS") if result.ok
                  else self._c(self.RED + self.BOLD, "FAIL"))
        self._emit(f"  {status}  {result.scenario}  ·  {result.elapsed:.1f}s "
                   f"(budget {result.budget:.0f}s)  ·  {result.steps_fired} steps")
        if result.max_drift > 1.0:
            self._emit(self._c(self.YELLOW, f"  max drift {result.max_drift:.1f}s — a beat ran long"))
        for f in result.failures:
            self._emit(self._c(self.RED, f"  ✘ {f}"))
        self._emit(self._c(self.BOLD, "─" * 72))
        self._emit()


def _compact(payload: dict[str, Any], limit: int = 88) -> str:
    if not payload:
        return ""
    parts = []
    for k, v in payload.items():
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "…"
        parts.append(f"{k}={s}")
    joined = " ".join(parts)
    return joined if len(joined) <= limit else joined[: limit - 1] + "…"


@dataclass
class RunResult:
    scenario: str
    ok: bool
    elapsed: float
    budget: float
    steps_fired: int
    max_drift: float
    failures: list[str] = field(default_factory=list)

    @property
    def over_budget(self) -> bool:
        return self.elapsed > self.budget


class DbSnapshot:
    """Pristine-DB snapshot + restore, stamped with a schema fingerprint.

    Snapshot at Hour 0 and after EVERY schema change. A stale snapshot restores
    a DB the current code cannot read — worse than no reset — so restore refuses
    a fingerprint mismatch unless overridden.
    """

    def __init__(self, db_path: Path, snapshot_path: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.snapshot_path = Path(snapshot_path or self.db_path.with_suffix(".pristine.db"))
        self._fingerprint_path = self.snapshot_path.with_suffix(".schema")

    def _schema_fingerprint(self, path: Path) -> str:
        import hashlib
        import sqlite3
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE sql IS NOT NULL ORDER BY type, name").fetchall()
        finally:
            con.close()
        blob = "\n".join(f"{t}|{n}|{s}" for t, n, s in rows).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def _checkpoint(self) -> None:
        import sqlite3
        con = sqlite3.connect(self.db_path)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con.commit()
        finally:
            con.close()

    def capture(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"cannot snapshot: {self.db_path} does not exist")
        self._checkpoint()
        shutil.copy2(self.db_path, self.snapshot_path)
        self._fingerprint_path.write_text(self._schema_fingerprint(self.snapshot_path))
        log.info("snapshot captured: %s", self.snapshot_path)

    def restore(self, *, strict: bool = True) -> None:
        if not self.snapshot_path.exists():
            raise FileNotFoundError(
                f"no snapshot at {self.snapshot_path}. "
                f"Run `python -m demo.run --snapshot` against a clean seeded DB first.")
        if strict and self._fingerprint_path.exists() and self.db_path.exists():
            expected = self._fingerprint_path.read_text().strip()
            actual = self._schema_fingerprint(self.db_path)
            if actual != expected:
                raise RuntimeError(
                    f"snapshot schema {expected} != live schema {actual}. "
                    f"Re-snapshot with `python -m demo.run --snapshot` "
                    f"(or pass --no-strict-snapshot to override).")
        for sidecar in ("-wal", "-shm"):
            Path(str(self.db_path) + sidecar).unlink(missing_ok=True)
        shutil.copy2(self.snapshot_path, self.db_path)
        log.info("db restored from %s", self.snapshot_path)


class ScenarioEngine:
    def __init__(
        self,
        *,
        inject_adapter: InjectAdapter,
        txn_replayer: TxnReplayer | None = None,
        sanctions_adapter: SanctionsAdapter | None = None,
        state_probe: StateProbe | None = None,
        console: Console | None = None,
        interactive: bool = True,
        rehearsal: bool = False,
    ) -> None:
        self.inject_adapter = inject_adapter
        self.txn_replayer = txn_replayer
        self.sanctions_adapter = sanctions_adapter
        self.state_probe = state_probe
        self.console = console or Console()
        self.interactive = interactive
        self.rehearsal = rehearsal

        self._handlers = {
            Action.INJECT_EVENT: self._h_inject_event,
            Action.START_TXN_REPLAY: self._h_start_txn_replay,
            Action.STOP_TXN_REPLAY: self._h_stop_txn_replay,
            Action.REFRESH_SANCTIONS: self._h_refresh_sanctions,
            Action.PAUSE: self._h_pause,
            Action.ASSERT_STATE: self._h_assert_state,
        }
        missing = set(Action) - set(self._handlers)
        if missing:
            raise RuntimeError(f"Action(s) without handler: {missing}")
        self._started_replays: list[str] = []

    async def _h_inject_event(self, **payload: Any) -> None:
        event_id = await self.inject_adapter.inject(**payload)
        self.console.ok(f"event injected → {event_id}")

    async def _h_start_txn_replay(self, **payload: Any) -> None:
        if self.txn_replayer is None:
            raise RuntimeError("start_txn_replay requires a txn_replayer")
        await self.txn_replayer.start(**payload)
        if entity := payload.get("entity"):
            self._started_replays.append(entity)
        self.console.ok(f"txn replay started · entity={payload.get('entity')} "
                        f"speed={payload.get('speed')}x")

    async def _h_stop_txn_replay(self, **payload: Any) -> None:
        if self.txn_replayer is None:
            return
        await self.txn_replayer.stop(**payload)
        self.console.ok("txn replay stopped")

    async def _h_refresh_sanctions(self, **payload: Any) -> None:
        if self.sanctions_adapter is None:
            raise RuntimeError("refresh_sanctions requires a sanctions_adapter")
        await self.sanctions_adapter.refresh(**payload)
        self.console.ok("sanctions list refreshed")

    async def _h_pause(self, *, message: str = "presenter beat", seconds: float = 3.0) -> None:
        if not self.interactive:
            await asyncio.sleep(min(seconds, 3.0))
            return
        self.console.pause_prompt(message)
        # input() blocks the loop; push to a thread so the replay clock and SSE
        # broadcasts keep running while the presenter talks — the point of pause.
        await asyncio.to_thread(sys.stdin.readline)

    async def _h_assert_state(self, **payload: Any) -> None:
        if not self.rehearsal:
            return
        if self.state_probe is None:
            raise RuntimeError("assert_state requires a state_probe in rehearsal mode")
        entity = payload.get("entity")
        if (want := payload.get("min_alerts")) is not None:
            got = await self.state_probe.alert_count(entity=entity)
            if got < want:
                raise AssertionError(f"expected >= {want} alerts for {entity}, got {got}")
        if (want := payload.get("band")) is not None:
            got = await self.state_probe.latest_alert_band(entity=entity)
            if got != want:
                raise AssertionError(f"expected band {want!r} for {entity}, got {got!r}")
        if (want := payload.get("min_sars")) is not None:
            got = await self.state_probe.sar_count(entity=entity)
            if got < want:
                raise AssertionError(f"expected >= {want} SARs for {entity}, got {got}")
        self.console.ok("state assertion passed")

    async def run(self, scenario: Scenario) -> RunResult:
        self.console.banner(scenario)
        failures: list[str] = []
        max_drift = 0.0
        fired = 0
        t0 = time.monotonic()
        paused_total = 0.0
        try:
            for step in scenario.steps:
                target = t0 + paused_total + step.at_seconds
                sleep_for = target - time.monotonic()
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                else:
                    drift = -sleep_for
                    max_drift = max(max_drift, drift)
                    if drift > 1.0:
                        self.console.warn(
                            f"running {drift:.1f}s behind at t={step.at_seconds}s — firing now")
                elapsed = time.monotonic() - t0
                self.console.narrate(elapsed, step)
                step_start = time.monotonic()
                try:
                    await self._handlers[step.action](**step.payload)
                except AssertionError as exc:
                    msg = f"t={step.at_seconds}s assert_state: {exc}"
                    self.console.fail(msg)
                    failures.append(msg)
                except Exception as exc:  # noqa: BLE001
                    msg = f"t={step.at_seconds}s {step.action.value}: {type(exc).__name__}: {exc}"
                    self.console.fail(msg)
                    failures.append(msg)
                    log.exception("step failed: %s", step.action.value)
                    if not self.rehearsal:
                        continue  # live demo: broken beat survivable, hung demo not
                finally:
                    if step.action is Action.PAUSE:
                        paused_total += time.monotonic() - step_start
                fired += 1
        finally:
            await self._cleanup()

        elapsed = time.monotonic() - t0
        result = RunResult(scenario=scenario.name, ok=not failures, elapsed=elapsed,
                           budget=scenario.budget_seconds, steps_fired=fired,
                           max_drift=max_drift, failures=failures)
        if result.over_budget:
            result.failures.append(f"OVER BUDGET: {elapsed:.1f}s > {scenario.budget_seconds:.0f}s")
            result.ok = False
        self.console.summary(result)
        return result

    async def _cleanup(self) -> None:
        # Always stop replay clocks — a leaked replay pollutes the next --reset.
        if self.txn_replayer is None:
            return
        for entity in self._started_replays:
            with contextlib.suppress(Exception):
                await self.txn_replayer.stop(entity=entity)
        self._started_replays.clear()