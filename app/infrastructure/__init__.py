"""Cross-cutting infrastructure: broker, cache, LLM gateway.

Nothing in here knows about entities, alerts or SARs. It is the plumbing every
other layer sits on, and it is the layer whose implementations get swapped in
Sprint 3 (mock LLM -> Gemini) without any caller changing.
"""

from app.infrastructure.broker import (
    ALERT_NEW,
    ALERT_UPDATED,
    ENTITY_UPDATED,
    SAR_READY,
    SYSTEM_HEALTH,
    TOPICS,
    AsyncioBroker,
    Message,
    UnknownTopicError,
    broker,
)
from app.infrastructure.cache import LocalMemoryCache
from app.infrastructure.llm_gateway import (
    GatewayResult,
    LLMClient,
    LLMDegradedError,
    LLMGateway,
)
from app.infrastructure.llm_mock import (
    MODEL_FALLBACK,
    MODEL_PRIMARY,
    MockLLMClient,
    MockLLMError,
)

__all__ = [
    # broker
    "AsyncioBroker",
    "Message",
    "UnknownTopicError",
    "broker",
    "TOPICS",
    "ALERT_NEW",
    "ALERT_UPDATED",
    "SAR_READY",
    "ENTITY_UPDATED",
    "SYSTEM_HEALTH",
    # cache
    "LocalMemoryCache",
    # gateway
    "LLMGateway",
    "GatewayResult",
    "LLMClient",
    "LLMDegradedError",
    # mock
    "MockLLMClient",
    "MockLLMError",
    "MODEL_PRIMARY",
    "MODEL_FALLBACK",
]