"""Core scenario types — Step, Scenario, and the action registry contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol


class Action(str, Enum):
    """Every action a scripted Step may fire.

    Adding a member here without a handler in ScenarioEngine._handlers fails at
    engine construction time, not mid-demo.
    """

    INJECT_EVENT = "inject_event"
    START_TXN_REPLAY = "start_txn_replay"
    STOP_TXN_REPLAY = "stop_txn_replay"
    REFRESH_SANCTIONS = "refresh_sanctions"
    PAUSE = "pause"
    ASSERT_STATE = "assert_state"  # rehearsal guardrail; no-op in live demo


@dataclass(frozen=True, slots=True)
class Step:
    at_seconds: float
    action: Action
    narration: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.at_seconds < 0:
            raise ValueError(f"Step at_seconds must be >= 0, got {self.at_seconds}")
        if not self.narration.strip():
            raise ValueError(f"Step at t={self.at_seconds} has empty narration")


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    title: str
    description: str
    steps: list[Step]
    budget_seconds: float = 240.0

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError(f"Scenario {self.name!r} has no steps")
        offsets = [s.at_seconds for s in self.steps]
        if offsets != sorted(offsets):
            raise ValueError(f"Scenario {self.name!r} steps not in order: {offsets}")
        scripted_end = offsets[-1]
        if scripted_end > self.budget_seconds:
            raise ValueError(
                f"Scenario {self.name!r} last step fires at t={scripted_end}s "
                f"but budget is {self.budget_seconds}s"
            )


class ScenarioContext(Protocol):
    async def inject_event(self, **payload: Any) -> str: ...
    async def start_txn_replay(self, **payload: Any) -> None: ...
    async def stop_txn_replay(self, **payload: Any) -> None: ...
    async def refresh_sanctions(self, **payload: Any) -> None: ...
    async def pause(self, **payload: Any) -> None: ...
    async def assert_state(self, **payload: Any) -> None: ...


StepHandler = Callable[..., Any]