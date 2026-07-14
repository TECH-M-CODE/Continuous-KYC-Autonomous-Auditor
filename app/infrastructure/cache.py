"""Process-local TTL cache.

Two callers, now and soon:

* ``LLMGateway`` — caches successful completions keyed on ``sha256(prompt+model)``.
  This is rung 3 of the degradation ladder: when both models are down, a cached
  answer for the same prompt is better than degrading to the review queue.
* ``SanctionsListAdapter`` (Sprint 2) — stores list ETags / last-modified headers.

Deliberately generic (``Any`` values, not dicts) so the second caller does not
force a rewrite. Deliberately not durable: a restart losing the cache is fine,
the ladder just falls through to rung 4.

Expiry is lazy — checked on read — rather than swept by a background task. A
sweeper is one more thing to start, stop and leak in the FastAPI lifespan, and
the cardinality here is small. ``purge_expired()`` is exposed for the rare caller
that wants to reclaim memory eagerly.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Final

log = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS: Final = 3600


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    misses: int
    expirations: int
    size: int

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


@dataclass(slots=True)
class _Entry:
    value: Any
    expires_at: float  # monotonic seconds


class LocalMemoryCache:
    """Dict-backed cache with per-key TTL and prefix invalidation.

    Thread-safe via a single lock. The gateway is async and single-threaded, but
    FastAPI runs sync endpoints in a threadpool and the Sprint 2 sanctions poller
    may well be a thread, so the lock is cheap insurance against a torn read.

    Uses ``time.monotonic`` rather than ``time.time``: a wall-clock adjustment
    (NTP step, container clock skew) must not silently expire or immortalise
    entries.
    """

    __slots__ = ("_store", "_lock", "_clock", "_hits", "_misses", "_expirations")

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._store: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._clock = clock  # injectable so tests do not sleep
        self._hits = 0
        self._misses = 0
        self._expirations = 0

    # ------------------------------------------------------------------------ get

    def get(self, key: str, default: Any = None) -> Any:
        """Return the live value for ``key``, or ``default`` if absent or expired.

        Note that a cached ``None`` is indistinguishable from a miss through this
        method by design — callers that need to cache a legitimate ``None`` should
        use a sentinel value. Nothing in CXKYC does.
        """
        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return default
            if entry.expires_at <= now:
                del self._store[key]
                self._expirations += 1
                self._misses += 1
                log.debug("cache expired: %s", key)
                return default
            self._hits += 1
            return entry.value

    def __contains__(self, key: str) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    # ------------------------------------------------------------------------ set

    def set(self, key: str, value: Any, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        """Store ``value`` under ``key`` for ``ttl_seconds``.

        A non-positive TTL is a caller bug (it would store an entry that is dead
        on arrival and merely burn memory until the next read), so it raises
        rather than silently no-op'ing.
        """
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        with self._lock:
            self._store[key] = _Entry(value=value, expires_at=self._clock() + ttl_seconds)

    # ----------------------------------------------------------------- invalidate

    def invalidate(self, prefix: str) -> int:
        """Drop every key starting with ``prefix``. Returns the number removed.

        Prefix-based rather than exact-key because callers namespace their keys
        (``llm:``, ``sanctions:``) and want to nuke a namespace wholesale — e.g.
        invalidating all cached LLM responses when ``policy.yaml`` changes.
        An empty prefix clears the cache; that is intentional, not an accident.
        """
        with self._lock:
            doomed = [k for k in self._store if k.startswith(prefix)]
            for key in doomed:
                del self._store[key]
        if doomed:
            log.info("invalidated %d cache entries under prefix %r", len(doomed), prefix)
        return len(doomed)

    def delete(self, key: str) -> bool:
        """Remove one exact key. Returns True if it was present."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = self._misses = self._expirations = 0

    # ---------------------------------------------------------------- maintenance

    def purge_expired(self) -> int:
        """Eagerly evict expired entries. Returns the count removed."""
        now = self._clock()
        with self._lock:
            doomed = [k for k, e in self._store.items() if e.expires_at <= now]
            for key in doomed:
                del self._store[key]
            self._expirations += len(doomed)
        return len(doomed)

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                expirations=self._expirations,
                size=len(self._store),
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


__all__ = ["LocalMemoryCache", "CacheStats", "DEFAULT_TTL_SECONDS"]