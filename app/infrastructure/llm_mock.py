"""Mock LLM client — the thing the gateway talks to until Sprint 3.

This file exists to make the degradation ladder *testable*, not merely present.
It exposes the exact surface the real Gemini client will expose
(``async generate(prompt, model, task_tag) -> str``), so Sprint 3 replaces the
client injected into ``LLMGateway`` and touches nothing else.

Three failure levers, all env-driven so tests and the demo can dial them:

* ``LLM_MOCK_FAIL_RATE``    — probability a call raises ``MockLLMError``.
                              At 1.0 every call fails and the ladder runs to rung 4.
* ``LLM_MOCK_INVALID_RATE`` — probability a call *succeeds* but returns JSON that
                              violates the caller's schema. This is a distinct
                              failure mode from a raised exception: it proves the
                              gateway treats validation failure as a call failure.
* ``LLM_MOCK_LATENCY_MS``   — per-call sleep, so exponential backoff is observable.

Determinism: the RNG is seedable. Tests seed it; the demo does not.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from typing import Any, Final

log = logging.getLogger(__name__)

MODEL_PRIMARY: Final = "gemini-3.1-flash-lite"
MODEL_FALLBACK: Final = "gemini-flash"


class MockLLMError(RuntimeError):
    """Simulates a transport/provider failure (timeout, 429, 5xx)."""


# Canned responses keyed on task_tag. Shapes mirror the Pydantic schemas the
# agents will pass to ``LLMGateway.complete(schema=...)`` in Sprint 3 — keep them
# in sync or the shape tests will (correctly) fail.
CANNED_RESPONSES: Final[dict[str, dict[str, Any]]] = {
    "resolver_verdict": {
        "match": True,
        "confidence": 0.93,
        "reasoning": (
            "Entity name and jurisdiction match the top candidate card; the "
            "director named in the article appears in the entity's known persons."
        ),
    },
    "classify_event": {
        # event_type must be a policy.yaml weight key (compute_delta() raises
        # otherwise); severity is a float in [0,1], not a band label -- both
        # previously violated ClassifyEventResult's schema, so every classify
        # call failed validation and silently degraded to defaults, 100% of
        # the time, regardless of LLM_MOCK_FAIL_RATE.
        "event_type": "adverse_media",
        "severity": 0.75,
        "evidence_summary": (
            "Adverse media report ties the entity to alleged procurement fraud; "
            "screening matched a name on record."
        ),
    },
    "sar_narrative": {
        "narrative": (
            "Between the reporting dates, the subject entity exhibited a pattern "
            "of structured transfers to counterparties in a FATF-listed "
            "jurisdiction, concurrent with adverse media alleging procurement "
            "fraud. The transaction velocity is inconsistent with the entity's "
            "declared sector and stated business purpose."
        ),
        "citations": [
            {"citation": "GDPR Art. 30", "passage": "Records of processing activities."},
            {"citation": "FATF Rec. 20", "passage": "Reporting of suspicious transactions."},
        ],
    },
}

# Returned when the invalid-response lever fires: syntactically valid JSON that
# no caller schema will accept (wrong keys, wrong types).
INVALID_RESPONSE: Final[dict[str, Any]] = {
    "unexpected_field": "this will not validate",
    "confidence": "not-a-float",
}


def _env_float(name: str, default: float, lo: float = 0.0, hi: float = 1.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        log.warning("%s=%r is not a float; using %s", name, raw, default)
        return default
    if not lo <= value <= hi:
        log.warning("%s=%s outside [%s, %s]; clamping", name, value, lo, hi)
        return max(lo, min(hi, value))
    return value


class MockLLMClient:
    """Drop-in stand-in for the Sprint 3 Gemini client.

    Config is read from the environment at construction, but every lever is also
    a constructor argument so tests can set them explicitly without touching
    ``os.environ`` (which leaks across tests).
    """

    __slots__ = ("fail_rate", "invalid_rate", "latency_s", "_rng", "call_log")

    def __init__(
        self,
        *,
        fail_rate: float | None = None,
        invalid_rate: float | None = None,
        latency_ms: float | None = None,
        seed: int | None = None,
    ) -> None:
        self.fail_rate = (
            fail_rate if fail_rate is not None else _env_float("LLM_MOCK_FAIL_RATE", 0.0)
        )
        self.invalid_rate = (
            invalid_rate
            if invalid_rate is not None
            else _env_float("LLM_MOCK_INVALID_RATE", 0.0)
        )
        latency = (
            latency_ms
            if latency_ms is not None
            else _env_float("LLM_MOCK_LATENCY_MS", 50.0, lo=0.0, hi=10_000.0)
        )
        self.latency_s = latency / 1000.0
        self._rng = random.Random(seed)
        # Every call recorded, so tests can assert *which* models the ladder tried
        # and in what order — not just that it eventually degraded.
        self.call_log: list[tuple[str, str]] = []  # (model, task_tag)

    async def generate(self, prompt: str, *, model: str, task_tag: str) -> str:
        """Return a raw JSON string, exactly as a real provider would.

        The gateway — not this client — owns parsing and schema validation, so
        returning a string keeps the mock honest about where the seam is.
        """
        self.call_log.append((model, task_tag))

        if self.latency_s:
            await asyncio.sleep(self.latency_s)

        if self._rng.random() < self.fail_rate:
            log.debug("mock LLM failing call to %s (%s)", model, task_tag)
            raise MockLLMError(f"simulated provider failure on {model}")

        if self._rng.random() < self.invalid_rate:
            log.debug("mock LLM returning schema-invalid payload for %s", task_tag)
            return json.dumps(INVALID_RESPONSE)

        try:
            payload = CANNED_RESPONSES[task_tag]
        except KeyError:
            raise MockLLMError(
                f"no canned response for task_tag {task_tag!r}; "
                f"known tags: {sorted(CANNED_RESPONSES)}"
            ) from None

        return json.dumps(payload)

    def reset(self) -> None:
        self.call_log.clear()


__all__ = [
    "MockLLMClient",
    "MockLLMError",
    "CANNED_RESPONSES",
    "INVALID_RESPONSE",
    "MODEL_PRIMARY",
    "MODEL_FALLBACK",
]