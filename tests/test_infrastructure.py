"""Dev 2's Definition of Done, executable.

The two DoD claims from the sprint plan are the two tests that must never go red:

* ``LLM_MOCK_FAIL_RATE=1.0`` -> ``complete()`` returns ``degraded=True`` and does
  NOT raise                                  -> ``test_ladder_degrades_without_raising``
* publish ``alert.new`` -> two subscribers both receive it
                                             -> ``test_broker_fans_out_to_two_subscribers``

Everything else here defends a property some future refactor will otherwise break.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.infrastructure.broker import (
    ALERT_NEW,
    SAR_READY,
    AsyncioBroker,
    UnknownTopicError,
)
from app.infrastructure.cache import LocalMemoryCache
from app.infrastructure.llm_gateway import (
    CACHE_PREFIX,
    GatewayResult,
    LLMDegradedError,
    LLMGateway,
)
from app.infrastructure.llm_mock import (
    MODEL_FALLBACK,
    MODEL_PRIMARY,
    MockLLMClient,
)

pytestmark = pytest.mark.asyncio


# --------------------------------------------------------------------------- #
# Fixtures & helpers
# --------------------------------------------------------------------------- #


class ResolverVerdict(BaseModel):
    """Mirrors the shape the Resolver agent will pass as ``schema=`` in Sprint 3."""

    match: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class FakeClock:
    """Manual clock, so TTL tests assert semantics instead of sleeping."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def _no_sleep(_seconds: float) -> None:
    """Injected in place of ``asyncio.sleep`` so backoff costs no wall-clock time."""
    return None


def _gateway(client: MockLLMClient, cache: LocalMemoryCache | None = None) -> LLMGateway:
    return LLMGateway(
        client=client,
        cache=cache if cache is not None else LocalMemoryCache(),
        sleep=_no_sleep,
    )


PROMPT = "Does 'Acme Holdings Ltd' in the article match entity card ENT-042?"


# --------------------------------------------------------------------------- #
# Broker
# --------------------------------------------------------------------------- #


async def test_broker_fans_out_to_two_subscribers() -> None:
    """DoD: publish alert.new, two subscribers both receive it."""
    broker = AsyncioBroker()
    left = broker.subscribe(ALERT_NEW)
    right = broker.subscribe(ALERT_NEW)

    delivered = broker.publish(ALERT_NEW, {"id": "alert-1", "band": "critical"})

    assert delivered == 2
    for queue in (left, right):
        message = await asyncio.wait_for(queue.get(), timeout=1)
        assert message.topic == ALERT_NEW
        assert message.payload["id"] == "alert-1"


async def test_publish_does_not_leak_across_topics() -> None:
    broker = AsyncioBroker()
    alerts = broker.subscribe(ALERT_NEW)
    sars = broker.subscribe(SAR_READY)

    broker.publish(ALERT_NEW, {"id": "alert-1"})

    assert alerts.qsize() == 1
    assert sars.empty()


async def test_subscribe_all_receives_every_topic_in_publish_order() -> None:
    """The SSE endpoint's exact usage: one queue, every topic, ordering preserved."""
    broker = AsyncioBroker()
    queue = broker.subscribe_all()

    broker.publish(ALERT_NEW, {"id": "alert-1"})
    broker.publish(SAR_READY, {"id": "sar-1"})

    first = await queue.get()
    second = await queue.get()

    assert (first.topic, second.topic) == (ALERT_NEW, SAR_READY)


async def test_full_subscriber_queue_drops_and_never_blocks_publisher() -> None:
    """The property the whole pipeline rests on.

    A wedged consumer (a closed browser tab nobody drains) must cost the producer
    nothing. If this ever starts awaiting, one dead client stalls ingestion.
    """
    broker = AsyncioBroker(maxsize=1)
    broker.subscribe(ALERT_NEW)  # never drained

    assert broker.publish(ALERT_NEW, {"id": "alert-1"}) == 1  # fills the queue
    assert broker.publish(ALERT_NEW, {"id": "alert-2"}) == 0  # dropped, not blocked

    assert broker.stats.dropped == 1
    assert broker.stats.published == 2


async def test_unsubscribe_is_idempotent() -> None:
    """A disconnected SSE client's ``finally`` block may run more than once."""
    broker = AsyncioBroker()
    queue = broker.subscribe(ALERT_NEW)

    broker.unsubscribe(ALERT_NEW, queue)
    broker.unsubscribe(ALERT_NEW, queue)  # must not raise

    assert broker.subscriber_count(ALERT_NEW) == 0
    assert broker.publish(ALERT_NEW, {"id": "alert-1"}) == 0


async def test_subscription_context_manager_cleans_up() -> None:
    broker = AsyncioBroker()
    with broker.subscription(ALERT_NEW) as queue:
        broker.publish(ALERT_NEW, {"id": "alert-1"})
        assert queue.qsize() == 1
    assert broker.subscriber_count(ALERT_NEW) == 0


async def test_unknown_topic_fails_loudly() -> None:
    """A typo'd topic must not silently never deliver."""
    broker = AsyncioBroker()
    with pytest.raises(UnknownTopicError):
        broker.publish("alert.created", {})  # not a real topic
    with pytest.raises(UnknownTopicError):
        broker.subscribe("alert.created")


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


async def test_cache_expires_entry_after_ttl() -> None:
    clock = FakeClock()
    cache = LocalMemoryCache(clock=clock)

    cache.set("k", "v", ttl_seconds=60)
    assert cache.get("k") == "v"

    clock.advance(59)
    assert cache.get("k") == "v", "must survive right up to the TTL boundary"

    clock.advance(2)
    assert cache.get("k") is None
    assert cache.stats().expirations == 1


async def test_cache_invalidate_matches_prefix_only() -> None:
    cache = LocalMemoryCache()
    cache.set("llm:aaa", 1, 60)
    cache.set("llm:bbb", 2, 60)
    cache.set("sanctions:ofac", 3, 60)

    removed = cache.invalidate("llm:")

    assert removed == 2
    assert cache.get("llm:aaa") is None
    assert cache.get("sanctions:ofac") == 3, "other namespaces must be untouched"


async def test_cache_rejects_non_positive_ttl() -> None:
    """A zero TTL is a caller bug — an entry dead on arrival — not a no-op."""
    cache = LocalMemoryCache()
    with pytest.raises(ValueError):
        cache.set("k", "v", ttl_seconds=0)


# --------------------------------------------------------------------------- #
# Gateway — the ladder, rung by rung
# --------------------------------------------------------------------------- #


async def test_rung_1_happy_path_uses_primary_model() -> None:
    client = MockLLMClient(fail_rate=0.0, latency_ms=0)
    result = await _gateway(client).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    assert result.ok is True
    assert result.degraded is False
    assert result.from_cache is False
    assert result.model_used == MODEL_PRIMARY
    assert result.attempts == 1
    assert isinstance(result.data, ResolverVerdict)
    assert result.data.confidence == pytest.approx(0.93)


async def test_rung_2_falls_back_to_second_model() -> None:
    """Primary exhausts its retries, fallback answers. Ladder advances, no degrade."""

    class PrimaryDownClient(MockLLMClient):
        async def generate(self, prompt: str, *, model: str, task_tag: str) -> str:
            if model == MODEL_PRIMARY:
                self.call_log.append((model, task_tag))
                raise RuntimeError("primary is down")
            return await super().generate(prompt, model=model, task_tag=task_tag)

    client = PrimaryDownClient(fail_rate=0.0, latency_ms=0)
    result = await _gateway(client).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    assert result.ok is True
    assert result.degraded is False
    assert result.model_used == MODEL_FALLBACK
    assert result.attempts == 3, "2 primary attempts + 1 successful fallback"
    assert [m for m, _ in client.call_log] == [
        MODEL_PRIMARY,
        MODEL_PRIMARY,
        MODEL_FALLBACK,
    ]


async def test_rung_3_serves_from_cache_when_both_models_are_down() -> None:
    """The rung people forget to test: a warm cache beats degrading to a human."""
    cache = LocalMemoryCache()

    warm = MockLLMClient(fail_rate=0.0, latency_ms=0)
    first = await _gateway(warm, cache).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )
    assert first.from_cache is False

    dead = MockLLMClient(fail_rate=1.0, latency_ms=0)
    second = await _gateway(dead, cache).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    assert second.ok is True
    assert second.from_cache is True
    assert second.degraded is False, "a cache hit is a real answer, not a degradation"
    assert second.data == first.data
    assert second.attempts == 4, "both models fully retried before the cache was consulted"


async def test_ladder_degrades_without_raising() -> None:
    """DoD: with a total provider outage and a cold cache, degrade — never raise."""
    client = MockLLMClient(fail_rate=1.0, latency_ms=0)

    result: GatewayResult = await _gateway(client).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    assert result.ok is False
    assert result.degraded is True
    assert result.data is None
    assert result.model_used is None
    assert result.attempts == 4, "2 primary + 2 fallback attempts before degrading"
    assert result.error is not None
    assert all(record.ok is False for record in result.trace)


async def test_schema_invalid_response_is_treated_as_a_call_failure() -> None:
    """A well-formed lie must advance the ladder exactly like a timeout.

    The model returns HTTP 200 and parseable JSON every time here — nothing raises
    at the transport layer. Only schema validation catches it. If this test fails,
    unvalidated model output is reaching the scoring engine.
    """
    client = MockLLMClient(fail_rate=0.0, invalid_rate=1.0, latency_ms=0)

    result = await _gateway(client).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    assert result.ok is False
    assert result.degraded is True
    assert result.attempts == 4, "validation failure consumed every rung's retries"
    assert "schema validation failed" in (result.error or "")


async def test_successful_response_is_cached_under_the_llm_namespace() -> None:
    cache = LocalMemoryCache()
    client = MockLLMClient(fail_rate=0.0, latency_ms=0)
    gateway = _gateway(client, cache)

    await gateway.complete(PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict")
    assert len(cache) == 1

    assert gateway.invalidate_cache() == 1
    assert len(cache) == 0


async def test_different_prompts_do_not_share_a_cache_entry() -> None:
    """Guards the cache key: hashing the model but not the prompt would be silent poison."""
    cache = LocalMemoryCache()
    client = MockLLMClient(fail_rate=0.0, latency_ms=0)
    gateway = _gateway(client, cache)

    await gateway.complete("prompt A", schema=ResolverVerdict, task_tag="resolver_verdict")
    await gateway.complete("prompt B", schema=ResolverVerdict, task_tag="resolver_verdict")

    assert len(cache) == 2, "same model, different prompt -> a different key"
    assert cache.invalidate(CACHE_PREFIX) == 2, "both live under the llm: namespace"


async def test_unwrap_raises_on_degraded_result() -> None:
    client = MockLLMClient(fail_rate=1.0, latency_ms=0)
    result = await _gateway(client).complete(
        PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict"
    )

    with pytest.raises(LLMDegradedError):
        result.unwrap()


async def test_missing_task_tag_is_a_programmer_error_and_raises() -> None:
    """Provider failures degrade; caller bugs raise. Keep the two distinguishable."""
    with pytest.raises(ValueError):
        await _gateway(MockLLMClient()).complete(PROMPT, schema=ResolverVerdict, task_tag="")


async def test_cancellation_is_never_swallowed_by_the_ladder() -> None:
    """A disconnected client must abort the call, not silently retry four times."""

    class HangingClient(MockLLMClient):
        async def generate(self, prompt: str, *, model: str, task_tag: str) -> str:
            await asyncio.sleep(30)
            raise AssertionError("unreachable")

    gateway = _gateway(HangingClient(latency_ms=0))
    task = asyncio.create_task(
        gateway.complete(PROMPT, schema=ResolverVerdict, task_tag="resolver_verdict")
    )
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task