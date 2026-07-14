"""Red-team drill (sequence 6.4). Stretch — run only after all 3 scenarios pass twice.

Samples watched + sanctioned names, uses ONE LLM call to generate evasion
variants (transliterations, typo-squats, shell names, split identities), injects
them all with is_drill=True, then verifies outcomes per variant class and writes
a drill report for Dev 5's DetectionHealth card.

CRITICAL SAFETY INVARIANT: drill events traverse the real pipeline but are
hard-blocked from creating real alerts/SARs. `assert_drill_isolation()` proves
this BEFORE any injection — a drill leaking real alerts mid-demo is a disaster.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol

log = logging.getLogger("demo.red_team")


class VariantClass(str, Enum):
    TRANSLITERATION = "transliteration"
    TYPO_SQUAT = "typo_squat"
    SHELL_NAME = "shell_name"
    SPLIT_IDENTITY = "split_identity"


@dataclass(frozen=True, slots=True)
class EvasionVariant:
    original: str
    variant: str
    variant_class: VariantClass
    #: Whether the pipeline is expected to catch this class. Transliterations and
    #: typo-squats should be caught by fuzzy screening; shell names and split
    #: identities are harder and a miss there is informative, not a failure.
    expected_caught: bool


@dataclass
class DrillOutcome:
    variant: EvasionVariant
    caught: bool
    detail: str = ""

    @property
    def as_expected(self) -> bool:
        return self.caught == self.variant.expected_caught


@dataclass
class DrillReport:
    started_at: str
    finished_at: str
    total: int
    caught: int
    by_class: dict[str, dict[str, int]] = field(default_factory=dict)
    misses: list[dict[str, Any]] = field(default_factory=list)
    isolation_verified: bool = False

    @property
    def headline(self) -> str:
        return f"{self.caught}/{self.total} evasion variants caught"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


class Gateway(Protocol):
    async def complete(self, prompt: str, *, schema: Any, task_tag: str) -> Any: ...


class DrillInjectAdapter(Protocol):
    async def inject(self, *, entity_name: str, is_drill: bool, **kw: Any) -> str: ...


class DrillProbe(Protocol):
    async def was_screened_hit(self, *, event_id: str) -> bool: ...
    async def real_alert_exists(self, *, event_id: str) -> bool: ...
    async def real_sar_exists(self, *, event_id: str) -> bool: ...


_VARIANT_PROMPT = """You are a financial-crime red-team assistant generating \
name-evasion variants to TEST a screening system's robustness. For each seed \
name produce up to {per_name} variants across these classes: transliteration, \
typo_squat, shell_name, split_identity.

Return ONLY JSON matching:
{{"variants": [{{"original": str, "variant": str, "variant_class": str}}]}}

Seed names:
{names}
"""


async def generate_variants(gateway: Gateway, names: list[str], *, per_name: int = 4,
                            schema: Any) -> list[EvasionVariant]:
    prompt = _VARIANT_PROMPT.format(per_name=per_name, names="\n".join(f"- {n}" for n in names))
    result = await gateway.complete(prompt, schema=schema, task_tag="red_team_variants")
    expected = {VariantClass.TRANSLITERATION: True, VariantClass.TYPO_SQUAT: True,
                VariantClass.SHELL_NAME: False, VariantClass.SPLIT_IDENTITY: False}
    out: list[EvasionVariant] = []
    for v in result.variants:
        try:
            vc = VariantClass(v.variant_class)
        except ValueError:
            log.warning("unknown variant_class %r, skipping", v.variant_class)
            continue
        out.append(EvasionVariant(v.original, v.variant, vc, expected[vc]))
    return out


async def assert_drill_isolation(inject: DrillInjectAdapter, probe: DrillProbe,
                                 *, canary_name: str = "__DRILL_CANARY__") -> None:
    """Prove drill isolation BEFORE the real drill. Inject one obvious hit as a
    drill; it must be screened (pipeline ran) but must NOT produce a real alert
    or SAR. Raises if the invariant is violated — refuse to run the drill."""
    event_id = await inject.inject(entity_name=canary_name, is_drill=True,
                                   event_type="adverse_media", source="red_team_canary",
                                   text=f"{canary_name} flagged for sanctions evasion.")
    screened = await probe.was_screened_hit(event_id=event_id)
    leaked_alert = await probe.real_alert_exists(event_id=event_id)
    leaked_sar = await probe.real_sar_exists(event_id=event_id)
    if leaked_alert or leaked_sar:
        raise RuntimeError(
            f"DRILL ISOLATION BREACH: canary produced "
            f"{'alert ' if leaked_alert else ''}{'sar' if leaked_sar else ''} — "
            f"aborting drill. A leaking drill flag would create real alerts in front "
            f"of judges.")
    if not screened:
        log.warning("canary not screened — pipeline may not be processing drill events")


async def run_drill(*, gateway: Gateway, inject: DrillInjectAdapter, probe: DrillProbe,
                    seed_names: list[str], variant_schema: Any, per_name: int = 4) -> DrillReport:
    started = datetime.now(timezone.utc).isoformat()
    await assert_drill_isolation(inject, probe)  # gate before any real injection

    variants = await generate_variants(gateway, seed_names, per_name=per_name, schema=variant_schema)
    outcomes: list[DrillOutcome] = []
    for v in variants:
        event_id = await inject.inject(entity_name=v.variant, is_drill=True,
                                       event_type="adverse_media", source="red_team",
                                       text=f"Adverse media naming {v.variant}.")
        caught = await probe.was_screened_hit(event_id=event_id)
        # Double-check no real alert/SAR leaked for this drill event either.
        if await probe.real_alert_exists(event_id=event_id):
            raise RuntimeError(f"DRILL LEAK on {v.variant!r} — real alert created")
        outcomes.append(DrillOutcome(v, caught))

    by_class: dict[str, dict[str, int]] = {}
    misses: list[dict[str, Any]] = []
    for o in outcomes:
        cls = o.variant.variant_class.value
        b = by_class.setdefault(cls, {"total": 0, "caught": 0})
        b["total"] += 1
        b["caught"] += int(o.caught)
        if not o.as_expected:
            misses.append({"variant": o.variant.variant, "class": cls,
                           "expected_caught": o.variant.expected_caught, "caught": o.caught})

    return DrillReport(
        started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
        total=len(outcomes), caught=sum(int(o.caught) for o in outcomes),
        by_class=by_class, misses=misses, isolation_verified=True)