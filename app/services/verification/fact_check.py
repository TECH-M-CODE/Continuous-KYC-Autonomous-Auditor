"""
app/services/verification/fact_check.py

Cross-source corroboration — Dev 2, Sprint 2.

An event about an entity is more believable when *different* sources reported it
independently inside a tight window. This module searches ``events_raw`` for
those neighbours and turns the count into a bounded confidence boost.

Rules (all tunable in policy.yaml):
  * window          : +/- 72h around the subject event's timestamp
  * same entity     : normalized-name match, rapidfuzz token_set_ratio >= 85
  * distinct source : same-source repeats never corroborate (syndication guard)
  * boost           : 0 sources = 0.00, 1 = +0.10, 2+ = +0.20 (saturates)

Pure logic against Sprint 1's repos: the only I/O is a read through the
``uow`` (unit of work). Pass ``candidates=`` to unit-test with zero DB.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

try:  # rapidfuzz is the project dep (Dev 4 uses it in screening.py too)
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - offline/dev fallback, same semantics
    class _Fuzz:
        @staticmethod
        def token_set_ratio(a: str, b: str) -> float:
            ta, tb = set(a.split()), set(b.split())
            if not ta or not tb:
                return 0.0
            inter = ta & tb
            s_i, s_a, s_b = " ".join(sorted(inter)), " ".join(sorted(inter | (ta - tb))), " ".join(sorted(inter | (tb - ta)))
            import difflib

            return max(
                difflib.SequenceMatcher(None, x, y).ratio()
                for x, y in ((s_i, s_a), (s_i, s_b), (s_a, s_b))
            ) * 100.0

    fuzz = _Fuzz()  # type: ignore[assignment]

from app.schemas.verification import CorroborationResult, CorroboratingSource
from app.services.verification.credibility import extract_domain

__all__ = ["corroborate", "normalize_name", "name_similarity"]

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

# Corporate suffixes are noise for identity matching: "Acme Holdings Ltd" and
# "Acme Holdings Limited" are the same party.
_LEGAL_SUFFIXES = {
    "ltd", "limited", "llc", "llp", "lp", "inc", "incorporated", "corp",
    "corporation", "co", "company", "plc", "pvt", "private", "gmbh", "ag",
    "sa", "sas", "nv", "bv", "spa", "srl", "pte", "holdings", "holding",
    "group", "intl", "international", "trust", "fze", "fzc", "dmcc", "jsc",
}


# --------------------------------------------------------------------------- #
# name normalization
# --------------------------------------------------------------------------- #
def normalize_name(name: str | None) -> str:
    """Casefold, strip punctuation/diacritic-noise and drop legal suffixes."""
    if not name:
        return ""
    text = _PUNCT_RE.sub(" ", str(name).lower())
    tokens = [t for t in _WS_RE.split(text) if t]
    core = [t for t in tokens if t not in _LEGAL_SUFFIXES]
    return " ".join(core or tokens)


def name_similarity(a: str | None, b: str | None) -> float:
    """token_set_ratio over normalized names, 0-100. Order-insensitive."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    return float(fuzz.token_set_ratio(na, nb))


# --------------------------------------------------------------------------- #
# accessors (RawEvent may be a model, a dict, or an ORM row)
# --------------------------------------------------------------------------- #
def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if obj.get(name) is not None:
                return obj[name]
            payload = obj.get("payload") or {}
            if isinstance(payload, dict) and payload.get(name) is not None:
                return payload[name]
        else:
            val = getattr(obj, name, None)
            if val is not None:
                return val
            payload = getattr(obj, "payload", None) or {}
            if isinstance(payload, dict) and payload.get(name) is not None:
                return payload[name]
    return default


def _cfg(policy: Any) -> Any:
    """Defaults to {} at any missing step -- see confidence.py's _cfg() for why:
    this nested block is optional and every caller goes through _c(), which
    already falls back to per-key defaults.
    """
    node = policy
    for key in ("verification", "corroboration"):
        if node is None:
            return {}
        node = node.get(key) if isinstance(node, dict) else getattr(node, key, None)
    return node if node is not None else {}


def _c(node: Any, key: str, default: Any = None) -> Any:
    return node.get(key, default) if isinstance(node, dict) else getattr(node, key, default)


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _event_names(event: Any) -> list[str]:
    """All name strings an event asserts: extracted candidates + entity name."""
    names: list[str] = []
    for field in ("name_candidates", "names", "matched_names", "entities"):
        vals = _get(event, field)
        if isinstance(vals, (list, tuple, set)):
            names.extend(str(v) for v in vals if v)
    for field in ("entity_name", "subject", "name"):
        val = _get(event, field)
        if isinstance(val, str) and val:
            names.append(val)
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        key = normalize_name(n)
        if key and key not in seen:
            seen.add(key)
            out.append(n)
    return out


def _source_key(event: Any) -> str:
    """Identity of a source for the distinctness test: domain, else source name."""
    url = _get(event, "url", "source_url", "link")
    domain = extract_domain(url if isinstance(url, str) else None)
    if domain:
        return domain
    src = _get(event, "source", "source_name", "adapter", default="unknown")
    return normalize_name(str(src)) or "unknown"


def _boost_for(count: int, cfg: Any) -> float:
    boosts = _c(cfg, "boosts", {}) or {}
    max_boost = float(_c(cfg, "max_boost", 0.20) or 0.20)
    table = {int(k): float(v) for k, v in dict(boosts).items()}
    if not table:
        return 0.0
    key = min(count, max(table))          # 2+ saturates on the highest tier
    return min(float(table.get(key, 0.0)), max_boost)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def corroborate(
    event: Any,
    uow: Any | None = None,
    policy: Any | None = None,
    *,
    candidates: Sequence[Any] | None = None,
) -> CorroborationResult:
    """Find distinct-source events about the same entity within +/- window_hours.

    Parameters
    ----------
    event      : the subject RawEvent (already screened).
    uow        : Sprint 1 unit-of-work; ``uow.events_raw`` supplies neighbours.
    policy     : hot-reloadable policy object.
    candidates : optional pre-fetched neighbour list — used by tests and by the
                 traced_pipeline when the events are already in hand. When
                 given, no DB read happens at all.
    """
    if policy is None:
        raise ValueError("corroborate() requires a policy object")

    cfg = _cfg(policy)
    window_hours = int(_c(cfg, "window_hours", 72) or 72)
    threshold = float(_c(cfg, "name_match_threshold", 85) or 85)
    require_distinct = bool(_c(cfg, "require_distinct_source", True))
    max_candidates = int(_c(cfg, "max_candidates", 200) or 200)

    subject_names = _event_names(event)
    subject_ts = _as_utc(
        _get(event, "published_at", "occurred_at", "created_at", "timestamp")
    ) or datetime.now(timezone.utc)
    subject_id = str(_get(event, "event_id", "id", default=""))
    subject_source = _source_key(event)
    subject_entity_id = _get(event, "entity_id", "resolved_entity_id")

    lo = subject_ts - timedelta(hours=window_hours)
    hi = subject_ts + timedelta(hours=window_hours)

    pool: Iterable[Any] = candidates if candidates is not None else _fetch(
        uow, subject_entity_id, lo, hi, max_candidates
    )

    matches: dict[str, CorroboratingSource] = {}   # source_key -> best match
    scanned = 0
    rejected_same_source = 0
    rejected_name = 0
    rejected_window = 0

    for cand in pool:
        scanned += 1
        if scanned > max_candidates:
            break

        cand_id = str(_get(cand, "event_id", "id", default=""))
        if cand_id and cand_id == subject_id:
            continue

        cand_ts = _as_utc(
            _get(cand, "published_at", "occurred_at", "created_at", "timestamp")
        )
        if cand_ts is None or not (lo <= cand_ts <= hi):
            rejected_window += 1
            continue

        cand_source = _source_key(cand)
        if require_distinct and cand_source == subject_source:
            rejected_same_source += 1
            continue

        best = 0.0
        for sn in subject_names:
            for cn in _event_names(cand):
                best = max(best, name_similarity(sn, cn))
        if best < threshold:
            rejected_name += 1
            continue

        hours_apart = abs((cand_ts - subject_ts).total_seconds()) / 3600.0
        existing = matches.get(cand_source)
        if existing is None or best > existing.name_match:
            matches[cand_source] = CorroboratingSource(
                event_id=cand_id or f"unknown:{cand_source}",
                source=str(_get(cand, "source", "source_name", "adapter", default=cand_source)),
                domain=extract_domain(_get(cand, "url", "source_url", "link")),
                published_at=cand_ts,
                name_match=round(best, 2),
                hours_apart=round(hours_apart, 2),
            )

    sources = sorted(matches.values(), key=lambda s: (-s.name_match, s.hours_apart))
    count = len(sources)
    boost = _boost_for(count, cfg)

    return CorroborationResult(
        corroborating_count=count,
        sources=sources,
        corroboration_boost=boost,
        window_hours=window_hours,
        breakdown={
            "window_hours": window_hours,
            "name_match_threshold": threshold,
            "require_distinct_source": require_distinct,
            "subject_source": subject_source,
            "subject_names": subject_names,
            "candidates_scanned": scanned,
            "corroborating_count": count,
            "corroborating_sources": [s.source for s in sources],
            "rejected": {
                "same_source": rejected_same_source,
                "name_below_threshold": rejected_name,
                "outside_window": rejected_window,
            },
            "corroboration_boost": boost,
        },
    )


def _fetch(uow: Any, entity_id: Any, lo: datetime, hi: datetime, limit: int) -> list[Any]:
    """Pull neighbour events from Sprint 1's repo layer, defensively.

    Repo method names differ across branches, so probe in order and degrade to
    an empty pool (no boost) rather than raising inside the pipeline.
    """
    if uow is None:
        return []
    repo = getattr(uow, "events_raw", None) or getattr(uow, "events", None)
    if repo is None:
        return []

    for method, kwargs in (
        ("list_in_window", {"entity_id": entity_id, "start": lo, "end": hi, "limit": limit}),
        ("find_in_window", {"entity_id": entity_id, "start": lo, "end": hi, "limit": limit}),
        ("list_by_entity", {"entity_id": entity_id, "limit": limit}),
        ("list_between", {"start": lo, "end": hi, "limit": limit}),
        ("list_recent", {"limit": limit}),
    ):
        fn = getattr(repo, method, None)
        if fn is None:
            continue
        try:
            return list(fn(**kwargs) or [])
        except TypeError:
            continue
        except Exception:
            return []
    return []