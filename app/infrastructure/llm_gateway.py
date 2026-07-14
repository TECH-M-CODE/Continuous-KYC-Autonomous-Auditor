"""LLM Gateway — every model call in CXKYC goes through here.

The gateway's reason for existing is the **degradation ladder**. In a compliance
system, "the LLM was down" is not an acceptable outcome; "the LLM was down, so
this item went to a human" is. The ladder makes that the default behaviour rather
than something each caller has to remember to write:

    rung 1  primary model    (gemini-3.1-flash-lite), retry x2, exponential backoff
    rung 2  fallback model   (gemini-flash),          retry x2, exponential backoff
    rung 3  cache            same prompt+model hash, previously successful
    rung 4  degrade          ok=False, degraded=True  -> caller routes to review queue

Two properties callers depend on, and which the tests pin:

* **complete() never raises for a provider failure.** It returns a
  ``GatewayResult`` with ``degraded=True``. A raise would force every agent to
  wrap every call in try/except and invent its own fallback, which is exactly the
  drift this class exists to prevent. (Programmer errors — an unknown task_tag, a
  bad schema — still raise, loudly.)

* **A schema-invalid response is a call failure.** If the model returns JSON that
  does not validate against the caller's Pydantic schema, that consumes an attempt
  and advances the ladder identically to a timeout. A well-formed lie is worse
  than an error, because it flows downstream into a SAR narrative.

Sprint 3: swap ``MockLLMClient`` for the real Gemini client. Nothing else changes —
the client protocol is one async method.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Final, Generic, Protocol, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.infrastructure.cache import DEFAULT_TTL_SECONDS, LocalMemoryCache
from app.infrastructure.llm_mock import MODEL_FALLBACK, MODEL_PRIMARY, MockLLMClient

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

CACHE_PREFIX: Final = "llm:"
DEFAULT_MAX_ATTEMPTS: Final = 2  # per model, per rung
DEFAULT_BACKOFF_BASE_S: Final = 0.2  # 0.2s, 0.4s, 0.8s ...
DEFAULT_CACHE_TTL_S: Final = DEFAULT_TTL_SECONDS


class LLMClient(Protocol):
    """The seam. Mock today, Gemini in Sprint 3 — one method either way."""

    async def generate(self, prompt: str, *, model: str, task_tag: str) -> str: ...


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    """One rung-1/rung-2 call. The audit trail for how a result was reached."""

    model: str
    ok: bool
    error: str | None
    elapsed_ms: float


@dataclass(slots=True)
class GatewayResult(Generic[T]):
    """The single return type of ``complete()``.

    ``ok`` and ``degraded`` are always inverses today, but they are kept separate
    because Sprint 3 may add a "succeeded, but on a weaker model" partial state
    that is ``ok=True, degraded=True``. Callers should branch on ``degraded``
    when deciding whether to involve a human, and on ``ok`` when deciding whether
    ``data`` is safe to read.
    """

    ok: bool
    data: T | None
    degraded: bool
    attempts: int
    model_used: str | None
    from_cache: bool
    task_tag: str = ""
    elapsed_ms: float = 0.0
    error: str | None = None
    trace: list[AttemptRecord] = field(default_factory=list)

    def unwrap(self) -> T:
        """Return ``data``, raising if the call degraded.

        For the small number of callers (scripts, tests) that genuinely have no
        degraded path. Agents must not use this — they must handle ``degraded``.
        """
        if not self.ok or self.data is None:
            raise LLMDegradedError(
                f"LLM call for {self.task_tag!r} degraded after {self.attempts} attempts: {self.error}"
            )
        return self.data


class LLMDegradedError(RuntimeError):
    """Raised only by ``GatewayResult.unwrap()``. ``complete()`` never raises this."""


class LLMGateway:
    """Retry → fallback → cache → degrade, in front of every model call."""

    __slots__ = (
        "_client",
        "_cache",
        "_primary",
        "_fallback",
        "_max_attempts",
        "_backoff_base",
        "_cache_ttl",
        "_sleep",
    )

    def __init__(
        self,
        client: LLMClient | None = None,
        cache: LocalMemoryCache | None = None,
        *,
        primary_model: str = MODEL_PRIMARY,
        fallback_model: str = MODEL_FALLBACK,
        max_attempts_per_model: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_S,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_S,
        sleep=asyncio.sleep,  # injectable: tests skip real backoff waits
    ) -> None:
        if max_attempts_per_model < 1:
            raise ValueError("max_attempts_per_model must be >= 1")
        self._client: LLMClient = client or MockLLMClient()
        self._cache = cache if cache is not None else LocalMemoryCache()
        self._primary = primary_model
        self._fallback = fallback_model
        self._max_attempts = max_attempts_per_model
        self._backoff_base = backoff_base_seconds
        self._cache_ttl = cache_ttl_seconds
        self._sleep = sleep

    # ----------------------------------------------------------------- public API

    async def complete(
        self,
        prompt: str,
        *,
        schema: Type[T],
        task_tag: str,
        use_cache: bool = True,
    ) -> GatewayResult[T]:
        """Run the ladder. Returns a result; does not raise on provider failure.

        ``schema`` is the Pydantic model the response must validate against. It is
        required, not optional: an unvalidated model response has no business
        reaching the scoring engine or a SAR narrative.
        """
        if not task_tag:
            raise ValueError("task_tag is required — it keys the mock, the cache, and the metrics")

        started = time.monotonic()
        trace: list[AttemptRecord] = []
        attempts = 0

        # ---- rungs 1 & 2: primary, then fallback -----------------------------
        for model in (self._primary, self._fallback):
            for attempt in range(1, self._max_attempts + 1):
                attempts += 1
                record, parsed = await self._try_once(prompt, model=model, schema=schema, task_tag=task_tag)
                trace.append(record)

                if record.ok and parsed is not None:
                    if use_cache:
                        self._cache.set(
                            self._cache_key(prompt, model), parsed.model_dump(), self._cache_ttl
                        )
                    return GatewayResult(
                        ok=True,
                        data=parsed,
                        degraded=False,
                        attempts=attempts,
                        model_used=model,
                        from_cache=False,
                        task_tag=task_tag,
                        elapsed_ms=self._elapsed_ms(started),
                        trace=trace,
                    )

                # Backoff between retries of the same model, but not before moving
                # to the next model — the fallback is a different provider path and
                # waiting there just adds latency to an already-slow request.
                if attempt < self._max_attempts:
                    await self._sleep(self._backoff_base * (2 ** (attempt - 1)))

            log.warning(
                "LLM rung exhausted for %s on %s after %d attempts; advancing ladder",
                task_tag,
                model,
                self._max_attempts,
            )

        # ---- rung 3: cache ---------------------------------------------------
        if use_cache:
            for model in (self._primary, self._fallback):
                cached = self._cache.get(self._cache_key(prompt, model))
                if cached is None:
                    continue
                try:
                    data = schema.model_validate(cached)
                except ValidationError:
                    # The cached entry predates a schema change. It is now poison;
                    # drop it rather than serving a shape the caller cannot read.
                    log.warning("stale cache entry for %s failed validation; evicting", task_tag)
                    self._cache.delete(self._cache_key(prompt, model))
                    continue

                log.info("LLM ladder served %s from cache (both models down)", task_tag)
                return GatewayResult(
                    ok=True,
                    data=data,
                    degraded=False,
                    attempts=attempts,
                    model_used=model,
                    from_cache=True,
                    task_tag=task_tag,
                    elapsed_ms=self._elapsed_ms(started),
                    trace=trace,
                )

        # ---- rung 4: degrade -------------------------------------------------
        last_error = trace[-1].error if trace else "no attempts made"
        log.error(
            "LLM ladder exhausted for %s after %d attempts; degrading to human review. Last error: %s",
            task_tag,
            attempts,
            last_error,
        )
        return GatewayResult(
            ok=False,
            data=None,
            degraded=True,
            attempts=attempts,
            model_used=None,
            from_cache=False,
            task_tag=task_tag,
            elapsed_ms=self._elapsed_ms(started),
            error=last_error,
            trace=trace,
        )

    # -------------------------------------------------------------------- internals

    async def _try_once(
        self, prompt: str, *, model: str, schema: Type[T], task_tag: str
    ) -> tuple[AttemptRecord, T | None]:
        """One call + parse + validate. Never raises; failures become records.

        Transport failure, malformed JSON, and schema violation are collapsed into
        the same outcome on purpose — from the ladder's point of view they are all
        "this rung did not produce a usable answer".
        """
        started = time.monotonic()
        try:
            raw = await self._client.generate(prompt, model=model, task_tag=task_tag)
        except asyncio.CancelledError:
            raise  # never swallow cancellation — the request is gone
        except Exception as exc:  # noqa: BLE001 - any provider error advances the ladder
            return (
                AttemptRecord(model, False, f"{type(exc).__name__}: {exc}", self._elapsed_ms(started)),
                None,
            )

        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            return (
                AttemptRecord(model, False, f"malformed JSON: {exc}", self._elapsed_ms(started)),
                None,
            )

        try:
            parsed = schema.model_validate(payload)
        except ValidationError as exc:
            # The load-bearing line. A confident, well-formed, wrong answer is the
            # dangerous failure in this system, so it is treated as a failed call.
            return (
                AttemptRecord(
                    model,
                    False,
                    f"schema validation failed: {exc.error_count()} error(s)",
                    self._elapsed_ms(started),
                ),
                None,
            )

        return AttemptRecord(model, True, None, self._elapsed_ms(started)), parsed

    @staticmethod
    def _cache_key(prompt: str, model: str) -> str:
        digest = hashlib.sha256(f"{prompt}\x00{model}".encode()).hexdigest()
        return f"{CACHE_PREFIX}{digest}"

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.monotonic() - started) * 1000, 2)

    def invalidate_cache(self) -> int:
        """Drop every cached completion. Call when prompts or policy.yaml change."""
        return self._cache.invalidate(CACHE_PREFIX)


__all__ = [
    "LLMGateway",
    "GatewayResult",
    "AttemptRecord",
    "LLMClient",
    "LLMDegradedError",
    "CACHE_PREFIX",
]