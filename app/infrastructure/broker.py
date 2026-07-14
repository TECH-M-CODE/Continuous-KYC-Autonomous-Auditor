"""In-process publish/subscribe broker built on asyncio queues.

The broker is the seam between producers (ingestion loops, agents) and consumers
(the SSE endpoint, background workers). It is deliberately in-process and
non-durable: Sprint 3 can swap it for Redis/NATS without any caller changing,
because callers only ever touch subscribe / publish / unsubscribe.

Design contract (agreed with Dev 4 at Hour 0 — do not change without a call):

    subscribe(topic)           -> asyncio.Queue[Message]
    subscribe_all()            -> asyncio.Queue[Message]   (one queue, every topic)
    unsubscribe(topic, queue)  -> None                     (idempotent)
    publish(topic, payload)    -> int                      (sync, NEVER blocks)

The single most important property: ``publish`` never blocks and never awaits.
A dead browser tab whose queue nobody drains must not stall the ingestion
pipeline, so a full subscriber queue drops the message and logs it rather than
applying backpressure. Alerts are re-derivable from the database; a stalled
pipeline is not.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Final

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Topics — a closed set, so a typo'd topic fails loudly instead of silently
# never delivering.
# --------------------------------------------------------------------------- #

ALERT_NEW: Final = "alert.new"
ALERT_UPDATED: Final = "alert.updated"
SAR_READY: Final = "sar.ready"
ENTITY_UPDATED: Final = "entity.updated"
SYSTEM_HEALTH: Final = "system.health"

TOPICS: Final[frozenset[str]] = frozenset(
    {ALERT_NEW, ALERT_UPDATED, SAR_READY, ENTITY_UPDATED, SYSTEM_HEALTH}
)

DEFAULT_QUEUE_MAXSIZE: Final = 100


class UnknownTopicError(KeyError):
    """Raised when a caller references a topic outside :data:`TOPICS`."""

    def __init__(self, topic: str) -> None:
        super().__init__(f"unknown topic {topic!r}; known topics: {sorted(TOPICS)}")
        self.topic = topic


# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Message:
    """What a subscriber pulls off its queue.

    Carrying the topic alongside the payload is what makes ``subscribe_all()``
    work with a single queue: the consumer still knows which event it got. The
    SSE layer maps ``topic`` straight onto the ``event:`` field of the stream.
    """

    topic: str
    payload: Any


@dataclass(slots=True)
class BrokerStats:
    """Counters for ``/health`` and for asserting drop behaviour in tests."""

    published: int = 0
    delivered: int = 0
    dropped: int = 0
    per_topic_published: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "published": self.published,
            "delivered": self.delivered,
            "dropped": self.dropped,
            "per_topic_published": dict(self.per_topic_published),
        }


# --------------------------------------------------------------------------- #
# Broker
# --------------------------------------------------------------------------- #


class AsyncioBroker:
    """Topic-based fan-out over :class:`asyncio.Queue`.

    Not thread-safe, by design — everything runs on one event loop. All mutation
    happens synchronously inside ``publish``/``subscribe``/``unsubscribe``, none
    of which contain an ``await``, so no lock is needed and none is taken.

    Example
    -------
    >>> broker = AsyncioBroker()
    >>> q = broker.subscribe(ALERT_NEW)
    >>> broker.publish(ALERT_NEW, {"id": "a-1"})
    1
    >>> msg = await q.get()
    >>> msg.topic, msg.payload
    ('alert.new', {'id': 'a-1'})
    """

    __slots__ = ("_maxsize", "_subs", "_stats")

    def __init__(self, maxsize: int = DEFAULT_QUEUE_MAXSIZE) -> None:
        if maxsize <= 0:
            raise ValueError("maxsize must be positive (0 means unbounded — that is the bug)")
        self._maxsize = maxsize
        # Insertion-ordered list per topic. A list is right here: subscriber
        # counts are in the single digits (one per open browser tab).
        self._subs: dict[str, list[asyncio.Queue[Message]]] = {t: [] for t in sorted(TOPICS)}
        self._stats = BrokerStats()

    # -- introspection ----------------------------------------------------- #

    @property
    def stats(self) -> BrokerStats:
        return self._stats

    def subscriber_count(self, topic: str | None = None) -> int:
        """Live queues on ``topic``, or across all topics when ``None``.

        Counts *subscriptions*, not subscribers: a queue registered via
        :meth:`subscribe_all` counts once per topic.
        """
        if topic is None:
            return sum(len(qs) for qs in self._subs.values())
        self._require_topic(topic)
        return len(self._subs[topic])

    # -- subscription ------------------------------------------------------ #

    def subscribe(self, topic: str, *, maxsize: int | None = None) -> asyncio.Queue[Message]:
        """Register a bounded queue for ``topic`` and return it.

        The caller owns the queue and must hand it back to :meth:`unsubscribe`
        when done, or the broker will keep enqueuing into it forever. Prefer
        :meth:`subscription` and let the context manager do that for you.
        """
        self._require_topic(topic)
        queue: asyncio.Queue[Message] = asyncio.Queue(
            maxsize=self._maxsize if maxsize is None else maxsize
        )
        self._subs[topic].append(queue)
        log.debug("subscribed to %s (now %d)", topic, len(self._subs[topic]))
        return queue

    def subscribe_all(self, *, maxsize: int | None = None) -> asyncio.Queue[Message]:
        """One queue fed by every topic — exactly what the SSE handler wants.

        Registering the *same* queue object against every topic, rather than N
        queues plus a merge task, buys two things: global publish ordering is
        preserved across topics, and there are no forwarding tasks to leak when
        the client disconnects.
        """
        queue: asyncio.Queue[Message] = asyncio.Queue(
            maxsize=self._maxsize if maxsize is None else maxsize
        )
        for subscribers in self._subs.values():
            subscribers.append(queue)
        log.debug("subscribed to all %d topics", len(self._subs))
        return queue

    def unsubscribe(self, topic: str | None, queue: asyncio.Queue[Message]) -> None:
        """Remove ``queue``. ``topic=None`` detaches it from every topic.

        Idempotent: removing an already-removed queue is a no-op, so the
        ``finally`` block of a disconnected SSE client can always call it.
        """
        if topic is not None:
            self._require_topic(topic)
        names = sorted(TOPICS) if topic is None else [topic]
        for name in names:
            try:
                self._subs[name].remove(queue)
            except ValueError:
                continue

    @contextmanager
    def subscription(
        self, topic: str | None = None, *, maxsize: int | None = None
    ) -> Iterator[asyncio.Queue[Message]]:
        """Scoped subscribe/unsubscribe — the safe way to consume.

        >>> with broker.subscription() as q:      # every topic
        ...     msg = await q.get()
        """
        queue = (
            self.subscribe_all(maxsize=maxsize)
            if topic is None
            else self.subscribe(topic, maxsize=maxsize)
        )
        try:
            yield queue
        finally:
            self.unsubscribe(topic, queue)

    # -- publication ------------------------------------------------------- #

    def publish(self, topic: str, payload: Any) -> int:
        """Fan ``payload`` out to every subscriber of ``topic``.

        Synchronous, non-blocking, and never raises because of a slow consumer.
        Returns the number of queues actually delivered to — useful in tests,
        ignorable in production.

        A full queue means the consumer is dead or wedged. Drop and log rather
        than await: awaiting here would let one stalled browser tab apply
        backpressure all the way up the ingestion pipeline, which is precisely
        the failure this broker exists to prevent.
        """
        self._require_topic(topic)

        message = Message(topic=topic, payload=payload)

        self._stats.published += 1
        self._stats.per_topic_published[topic] = (
            self._stats.per_topic_published.get(topic, 0) + 1
        )

        delivered = 0
        for queue in self._subs[topic]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                self._stats.dropped += 1
                log.warning(
                    "dropped %s: subscriber queue full (maxsize=%d) — consumer is not draining",
                    topic,
                    queue.maxsize,
                )
            else:
                delivered += 1

        self._stats.delivered += delivered
        return delivered

    # -- lifecycle --------------------------------------------------------- #

    def reset(self) -> None:
        """Drop every subscription and zero the counters.

        For lifespan shutdown and test isolation only — never call this from
        request handling.
        """
        for subscribers in self._subs.values():
            subscribers.clear()
        self._stats = BrokerStats()

    # -- internals --------------------------------------------------------- #

    @staticmethod
    def _require_topic(topic: str) -> None:
        if topic not in TOPICS:
            raise UnknownTopicError(topic)


# --------------------------------------------------------------------------- #
# Module singleton — import this, do not construct your own.
#   from app.infrastructure.broker import broker, ALERT_NEW
# --------------------------------------------------------------------------- #

broker: Final[AsyncioBroker] = AsyncioBroker()


__all__ = [
    "AsyncioBroker",
    "Message",
    "BrokerStats",
    "UnknownTopicError",
    "broker",
    "TOPICS",
    "ALERT_NEW",
    "ALERT_UPDATED",
    "SAR_READY",
    "ENTITY_UPDATED",
    "SYSTEM_HEALTH",
    "DEFAULT_QUEUE_MAXSIZE",
]