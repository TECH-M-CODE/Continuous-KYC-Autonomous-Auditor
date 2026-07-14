"""Demo scenario engine.

TWO modes, one module:

**Legacy (unchanged, still the default for HTTP):** ``run_scenario(name)``
injects a fixed batch of events and runs the pipeline over them immediately.
Fast, non-interactive, no clock. Used by ``POST /api/v1/pipeline/demo``.

- ``sanctions_hit``        — entity matches OFAC SDN list, high severity
- ``adverse_media_spike``  — burst of adverse news articles, velocity spike
- ``transaction_velocity`` — structuring-pattern transaction anomaly

**Timed (new, Sprint 3):** ``ScenarioEngine.run(Scenario)`` executes a scripted,
pause-gated, narrated performance against an absolute clock. Used by
``python -m demo.run money_laundering``. Presenter reads the narration cues off
the console; PAUSE steps hold the clock while they talk.

The two share the injection path (``persist_events`` → ``run_pipeline``), so a
timed scenario's ``inject_event`` step lands in exactly the same pipeline the
legacy runner uses. Nothing about the legacy contract changed.

Usage (programmatic, legacy):
    from demo.scenario_engine import run_scenario
    await run_scenario("sanctions_hit")

Usage (HTTP, legacy):
    POST /api/v1/pipeline/demo  {"scenario": "sanctions_hit"}

Usage (timed):
    python -m demo.run money_laundering --reset
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from app.models.events import RawEvent
from app.repositories.unit_of_work import UnitOfWork
from app.services.ingestion.base import IngestedEvent, persist_events

from demo.types import Action, Scenario, Step

log = logging.getLogger(__name__)

ScenarioName = Literal["sanctions_hit", "adverse_media_spike", "transaction_velocity"]


# ═════════════════════════════════════════════════════════════════════════════
# PART 1 — Legacy batch scenarios. UNCHANGED.
# ═════════════════════════════════════════════════════════════════════════════

# ── Scenario definitions ─────────────────────────────────────────────────────

def _get_first_entity_id() -> str | None:
    """Grab the first entity in the DB to use as a realistic target."""
    with UnitOfWork() as uow:
        entities = uow.entities.list()
        return entities[0].id if entities else None


def _make_sanctions_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="sanctions_hit",
            source="ofac_sdn",
            title="OFAC SDN Match: Viktor Petrov",
            text=(
                "The Office of Foreign Assets Control (OFAC) has added Viktor Petrov, "
                "a director of Acme Import Export Ltd, to the Specially Designated "
                "Nationals (SDN) list effective immediately. The designation is related "
                "to procurement fraud and illicit financing activities in FATF-listed "
                "jurisdictions. All US persons are prohibited from transacting with "
                "this individual and associated entities."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 1.0},
            source_url="https://sanctionssearch.ofac.treas.gov/Details.aspx?id=99999",
            entity_hint=entity_id,
        )
    ]


def _make_adverse_media_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="adverse_media_fraud",
            source="reuters",
            title="Investigation: Shell company network linked to money laundering",
            text=(
                "A Reuters investigation has uncovered a network of shell companies "
                "connected to Acme Import Export Ltd. According to sources familiar "
                "with the matter, the network was used to funnel proceeds from "
                "procurement fraud through multiple FATF-listed jurisdictions. "
                "The company's director Viktor Petrov is named as a person of "
                "interest in an ongoing criminal investigation."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 0.85},
            source_url="https://reuters.com/investigation/shell-company-network",
            entity_hint=entity_id,
        ),
        IngestedEvent(
            event_type="adverse_media",
            source="financial_times",
            title="Regulatory scrutiny intensifies for cross-border trade entities",
            text=(
                "Multiple regulatory bodies across the EU and UK are intensifying "
                "scrutiny of cross-border trade entities following the emergence of "
                "the Petrov network revelations. Compliance officers are urged to "
                "review correspondent relationships with entities operating in "
                "higher-risk jurisdictions."
            ),
            occurred_at=now,
            payload={"entity_name": "Acme Import Export Ltd", "severity": 0.6},
            entity_hint=entity_id,
        ),
    ]


def _make_transaction_velocity_events(entity_id: str | None) -> list[IngestedEvent]:
    now = datetime.now(timezone.utc)
    return [
        IngestedEvent(
            event_type="transaction_anomaly",
            source="internal_transaction_monitor",
            title="Transaction velocity anomaly: 3x baseline within 24h",
            text=(
                "The internal transaction monitoring system has flagged Acme Import Export Ltd "
                "for a velocity spike: 12 cross-border wire transfers totalling approximately "
                "USD 3.2M were processed in a 24-hour window, representing 3.1x the entity's "
                "established 90-day baseline. The counterparties include entities in jurisdictions "
                "with elevated FATF risk ratings. A structuring pattern cannot be ruled out pending "
                "further review."
            ),
            occurred_at=now,
            payload={
                "entity_name": "Acme Import Export Ltd",
                "severity": 0.8,
                "transaction_count": 12,
                "total_amount_usd": 3_200_000,
                "window_hours": 24,
                "velocity_multiplier": 3.1,
            },
            entity_hint=entity_id,
        )
    ]


_SCENARIO_MAP = {
    "sanctions_hit": _make_sanctions_events,
    "adverse_media_spike": _make_adverse_media_events,
    "transaction_velocity": _make_transaction_velocity_events,
}

# ── Runner ────────────────────────────────────────────────────────────────────

async def run_scenario(scenario: ScenarioName, entity_id: str | None = None) -> dict:
    """Inject scenario events and run the full pipeline. Returns a summary dict.

    Parameters
    ----------
    scenario:
        One of ``"sanctions_hit"``, ``"adverse_media_spike"``, ``"transaction_velocity"``.
    entity_id:
        Override target entity. Defaults to the first entity in the DB.
    """
    from app.agents.supervisor import run_pipeline

    if scenario not in _SCENARIO_MAP:
        raise ValueError(f"Unknown scenario {scenario!r}. Known: {sorted(_SCENARIO_MAP)}")

    target_entity_id = entity_id or _get_first_entity_id()
    log.info("scenario_engine: running '%s' against entity=%s", scenario, target_entity_id)

    # 1. Inject events
    events = _SCENARIO_MAP[scenario](target_entity_id)
    new_count = persist_events(events)
    log.info("scenario_engine: persisted %d new event(s)", new_count)

    # 2. Fetch the just-persisted events (they are PENDING / unprocessed)
    results = []
    with UnitOfWork() as uow:
        pending = uow.events.get_unprocessed(limit=len(events) + 5)
        scenario_events = pending[: len(events)]

    for raw_event in scenario_events:
        state = await run_pipeline(raw_event)
        results.append({
            "event_id": raw_event.id,
            "final_outcome": state.get("final_outcome"),
            "alert_id": state.get("alert_id"),
            "sar_id": state.get("sar_id"),
            "confidence": state.get("confidence"),
            "risk_band": state.get("risk_band"),
            "error": state.get("error"),
        })

    return {
        "scenario": scenario,
        "entity_id": target_entity_id,
        "events_injected": len(events),
        "results": results,
    }


# ═════════════════════════════════════════════════════════════════════════════
# PART 2 — Timed scenario engine (Sprint 3, Dev 2).
#
# Design notes:
#  * Monotonic clock, ABSOLUTE schedule. Each step sleeps until its offset from
#    t0. Sleeping the delta between beats accumulates drift (an LLM call inside
#    a step pushes every later beat back); anchoring to t0 does not. If a step
#    overruns we warn and fire the next beat immediately rather than silently
#    stretching a 4-minute demo into 6.
#  * PAUSE steps are wall-clock-free: paused time is subtracted from the
#    schedule, so a long ad-lib does not make the remaining beats fire at once.
#  * Collaborators are INJECTED. Tests pass fakes; demo/run.py passes the real
#    stack. That is what lets Dev 2 dry-run the engine before the graph lands.
# ═════════════════════════════════════════════════════════════════════════════

# ── Collaborator protocols ───────────────────────────────────────────────────

class InjectAdapter(Protocol):
    async def inject(
        self,
        *,
        event_type: str,
        entity_name: str,
        text: str,
        source: str,
        title: str = "",
        severity: float = 0.5,
        is_drill: bool = False,
        **extra: Any,
    ) -> str:
        """Push one RawEvent through the pipeline. Returns the event id."""
        ...


class TxnReplayer(Protocol):
    async def start(self, *, entity: str, speed: float, **kw: Any) -> None: ...
    async def stop(self, *, entity: str | None = None) -> None: ...


class SanctionsAdapter(Protocol):
    async def refresh(self, *, planted_addition: dict[str, Any] | None = None) -> None: ...


class StateProbe(Protocol):
    async def alert_count(self, *, entity: str | None = None) -> int: ...
    async def latest_alert_band(self, *, entity: str) -> str | None: ...
    async def sar_count(self, *, entity: str | None = None) -> int: ...


# ── Real InjectAdapter, built on the SAME path run_scenario() uses ───────────

class PipelineInjectAdapter:
    """Live inject adapter: persist_events → run_pipeline.

    Deliberately reuses ``persist_events`` and ``app.agents.supervisor.run_pipeline``
    so a timed scenario's events traverse the identical pipeline as the legacy
    batch scenarios. One injection path, one set of bugs.

    ``is_drill`` rides on the payload so the pipeline's drill hard-block (Dev 2's
    red-team guard) can see it. It defaults False and must be passed explicitly —
    a scenario cannot accidentally inherit drill mode.
    """

    def __init__(self, *, entity_id: str | None = None, await_pipeline: bool = True) -> None:
        #: Target entity for entity_hint. Defaults to the first DB entity,
        #: matching legacy run_scenario() behaviour.
        self._entity_id = entity_id or _get_first_entity_id()
        #: await_pipeline=False fires the pipeline as a background task, so the
        #: engine's clock does not block on a slow LLM call. Set True in tests
        #: and rehearsal where determinism matters more than timing fidelity.
        self._await_pipeline = await_pipeline
        self._tasks: list[asyncio.Task] = []

    async def inject(
        self,
        *,
        event_type: str,
        entity_name: str,
        text: str,
        source: str,
        title: str = "",
        severity: float = 0.5,
        is_drill: bool = False,
        **extra: Any,
    ) -> str:
        from app.agents.supervisor import run_pipeline

        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "entity_name": entity_name,
            "severity": severity,
            "is_drill": is_drill,
            **extra,
        }
        ingested = IngestedEvent(
            event_type=event_type,
            source=source,
            title=title or f"{event_type}: {entity_name}",
            text=text,
            occurred_at=now,
            payload=payload,
            entity_hint=self._entity_id,
        )
        persist_events([ingested])

        with UnitOfWork() as uow:
            pending = uow.events.get_unprocessed(limit=5)
        if not pending:
            raise RuntimeError(
                f"injected {event_type!r} for {entity_name!r} but no unprocessed event "
                f"came back — persist_events may have deduped it. If you are re-running "
                f"without --reset, restore the pristine DB first."
            )
        raw_event: RawEvent = pending[0]

        if self._await_pipeline:
            await run_pipeline(raw_event)
        else:
            task = asyncio.create_task(self._run_guarded(run_pipeline, raw_event))
            self._tasks.append(task)
        return raw_event.id

    async def _run_guarded(self, run_pipeline, raw_event: RawEvent) -> None:
        # A background pipeline failure must surface in the console, not vanish
        # into a never-awaited task.
        try:
            await run_pipeline(raw_event)
        except Exception:  # noqa: BLE001
            log.exception("background pipeline failed for event %s", raw_event.id)

    async def drain(self, timeout: float = 30.0) -> None:
        """Wait for in-flight background pipelines. Called at scenario cleanup so
        a rehearsal's assertions do not race the work they are asserting on."""
        if not self._tasks:
            return
        done, pending = await asyncio.wait(self._tasks, timeout=timeout)
        for t in pending:
            t.cancel()
        self._tasks.clear()


# ── Console — narration is a first-class output, not logging ─────────────────

class Console:
    """The co-presenter reads this. Keep it clean."""

    DIM, BOLD = "\033[2m", "\033[1m"
    CYAN, GREEN, YELLOW, RED, RESET = "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[0m"

    def __init__(self, *, color: bool = True, stream=sys.stdout) -> None:
        self._color = color and hasattr(stream, "isatty") and stream.isatty()
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
        self._emit(f"{stamp}  {self._c(self.CYAN + self.BOLD, step.narration)}")
        self._emit(self._c(self.DIM,
                   f"            └─ {step.action.value}  {_compact(step.payload)}"))

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

    def summary(self, result: RunResult) -> None:
        self._emit()
        self._emit(self._c(self.BOLD, "─" * 72))
        status = (self._c(self.GREEN + self.BOLD, "PASS") if result.ok
                  else self._c(self.RED + self.BOLD, "FAIL"))
        self._emit(f"  {status}  {result.scenario}  ·  {result.elapsed:.1f}s "
                   f"(budget {result.budget:.0f}s)  ·  {result.steps_fired} steps")
        if result.max_drift > 1.0:
            self._emit(self._c(self.YELLOW,
                       f"  max drift {result.max_drift:.1f}s — a beat ran long"))
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
        parts.append(f"{k}={s[:37] + '…' if len(s) > 40 else s}")
    joined = " ".join(parts)
    return joined if len(joined) <= limit else joined[: limit - 1] + "…"


# ── Result ───────────────────────────────────────────────────────────────────

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


# ── DB snapshot / --reset ────────────────────────────────────────────────────

class DbSnapshot:
    """Pristine-DB snapshot + restore, stamped with a schema fingerprint.

    Snapshot at Hour 0 and after EVERY schema change. A stale snapshot restores a
    DB the current code cannot read — worse than no reset at all — so restore
    refuses a fingerprint mismatch unless explicitly overridden.
    """

    def __init__(self, db_path: Path, snapshot_path: Path | None = None) -> None:
        self.db_path = Path(db_path)
        self.snapshot_path = Path(snapshot_path or self.db_path.with_suffix(".pristine.db"))
        self._fingerprint_path = self.snapshot_path.with_suffix(".schema")

    def _schema_fingerprint(self, path: Path) -> str:
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
                f"no snapshot at {self.snapshot_path}. Run "
                f"`python -m demo.run --snapshot` against a clean seeded DB first.")
        if strict and self._fingerprint_path.exists() and self.db_path.exists():
            expected = self._fingerprint_path.read_text().strip()
            actual = self._schema_fingerprint(self.db_path)
            if actual != expected:
                raise RuntimeError(
                    f"snapshot schema {expected} != live schema {actual}. The schema "
                    f"changed since the snapshot was taken. Re-snapshot with "
                    f"`python -m demo.run --snapshot` (or --no-strict-snapshot to override).")
        for sidecar in ("-wal", "-shm"):
            Path(str(self.db_path) + sidecar).unlink(missing_ok=True)
        shutil.copy2(self.snapshot_path, self.db_path)
        log.info("db restored from %s", self.snapshot_path)


# ── Engine ───────────────────────────────────────────────────────────────────

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
        #: interactive=False turns PAUSE into a short sleep, so CI and --auto
        #: rehearsals never hang on a keypress.
        self.interactive = interactive
        #: rehearsal=True enforces ASSERT_STATE. In the live demo assertions are
        #: skipped — an assertion failure must never abort the performance.
        self.rehearsal = rehearsal

        self._handlers = {
            Action.INJECT_EVENT: self._h_inject_event,
            Action.START_TXN_REPLAY: self._h_start_txn_replay,
            Action.STOP_TXN_REPLAY: self._h_stop_txn_replay,
            Action.REFRESH_SANCTIONS: self._h_refresh_sanctions,
            Action.PAUSE: self._h_pause,
            Action.ASSERT_STATE: self._h_assert_state,
        }
        if missing := set(Action) - set(self._handlers):
            raise RuntimeError(f"Action(s) without handler: {missing}")
        self._started_replays: list[str] = []

    # -- handlers ------------------------------------------------------------

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
        # broadcasts keep running while the presenter talks — the point of PAUSE.
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
        if (want := payload.get("max_alerts")) is not None:
            got = await self.state_probe.alert_count(entity=entity)
            if got > want:
                raise AssertionError(f"expected <= {want} alerts for {entity}, got {got}")
        if (want := payload.get("band")) is not None:
            got = await self.state_probe.latest_alert_band(entity=entity)
            if got != want:
                raise AssertionError(f"expected band {want!r} for {entity}, got {got!r}")
        if (want := payload.get("min_sars")) is not None:
            got = await self.state_probe.sar_count(entity=entity)
            if got < want:
                raise AssertionError(f"expected >= {want} SARs for {entity}, got {got}")
        self.console.ok("state assertion passed")

    # -- run -----------------------------------------------------------------

    async def run(self, scenario: Scenario) -> RunResult:
        self.console.banner(scenario)
        failures: list[str] = []
        max_drift, fired = 0.0, 0
        t0 = time.monotonic()
        paused_total = 0.0

        try:
            for step in scenario.steps:
                sleep_for = (t0 + paused_total + step.at_seconds) - time.monotonic()
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                else:
                    drift = -sleep_for
                    max_drift = max(max_drift, drift)
                    if drift > 1.0:
                        self.console.warn(
                            f"running {drift:.1f}s behind at t={step.at_seconds}s — firing now")

                self.console.narrate(time.monotonic() - t0, step)
                step_start = time.monotonic()
                try:
                    await self._handlers[step.action](**step.payload)
                except AssertionError as exc:
                    # Record and keep going: one bad beat must not hide the three
                    # bugs behind it.
                    msg = f"t={step.at_seconds}s assert_state: {exc}"
                    self.console.fail(msg)
                    failures.append(msg)
                except Exception as exc:  # noqa: BLE001
                    msg = f"t={step.at_seconds}s {step.action.value}: {type(exc).__name__}: {exc}"
                    self.console.fail(msg)
                    failures.append(msg)
                    log.exception("step failed: %s", step.action.value)
                    if not self.rehearsal:
                        continue  # live: a broken beat is survivable, a hung demo is not
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
            result.failures.append(
                f"OVER BUDGET: {elapsed:.1f}s > {scenario.budget_seconds:.0f}s")
            result.ok = False
        self.console.summary(result)
        return result

    async def _cleanup(self) -> None:
        """Always stop replay clocks and drain background pipelines. A leaked
        replay pollutes the next --reset run and turns a clean rerun flaky."""
        if self.txn_replayer is not None:
            for entity in self._started_replays:
                with contextlib.suppress(Exception):
                    await self.txn_replayer.stop(entity=entity)
            self._started_replays.clear()
        drain = getattr(self.inject_adapter, "drain", None)
        if drain is not None:
            with contextlib.suppress(Exception):
                await drain()


__all__ = [
    # legacy — unchanged public surface
    "run_scenario",
    "ScenarioName",
    # timed engine
    "ScenarioEngine",
    "PipelineInjectAdapter",
    "Console",
    "DbSnapshot",
    "RunResult",
    "InjectAdapter",
    "TxnReplayer",
    "SanctionsAdapter",
    "StateProbe",
]