"""
app/services/verification/credibility.py

Source credibility scoring — Dev 2, Sprint 2.

Pure and deterministic: same RawEvent, same float, no I/O, no LLM. The only
input besides the event is the policy object (hot-reloadable, Dev 1's loader).

Resolution ladder, first hit wins:
    1. explicit domain -> tier   (policy.verification.credibility.domain_tiers)
    2. adapter/source -> tier    (policy.verification.credibility.source_tiers)
    3. default 0.5 + low_credibility flag

Heuristic adjustments (missing author, opinion markers) are then applied and the
result is clamped to [0, 1].
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.schemas.verification import CredibilityResult

__all__ = ["score_source", "extract_domain", "resolve_tier"]

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def extract_domain(value: str | None) -> str | None:
    """Return the lowercase registrable-ish domain from a URL or bare host.

    ``https://news.reuters.com/x?y=1`` -> ``news.reuters.com``
    ``Reuters`` -> ``None`` (not a domain — falls through to the source table)
    """
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if not _SCHEME_RE.match(raw):
        # Bare host only if it plausibly looks like one.
        if "." not in raw or " " in raw:
            return None
        raw = "//" + raw
    host = urlparse(raw, scheme="https").hostname
    if not host:
        return None
    host = host.lower().lstrip(".")
    return host[4:] if host.startswith("www.") else host


def _suffix_lookup(domain: str, table: dict[str, str]) -> tuple[str, str] | None:
    """Match ``news.reuters.com`` against a ``reuters.com`` key.

    Longest key wins, so ``ofac.treasury.gov`` beats ``treasury.gov``.
    """
    best: tuple[str, str] | None = None
    for key, tier in table.items():
        k = key.lower()
        if domain == k or domain.endswith("." + k):
            if best is None or len(k) > len(best[0]):
                best = (k, tier)
    return best


def _norm_source_key(source: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (source or "").strip().lower()).strip("_")


def _cfg(policy: Any) -> Any:
    """Accept either a Pydantic RiskPolicy or a plain dict.

    Defaults to {} at any missing step -- this nested block is optional
    (RiskPolicy today has no ``verification`` field at all), and every caller
    goes through ``_get()``, which already falls back to per-key defaults.
    """
    node = policy
    for key in ("verification", "credibility"):
        if node is None:
            return {}
        node = node.get(key) if isinstance(node, dict) else getattr(node, key, None)
    return node if node is not None else {}


def _get(node: Any, key: str, default: Any = None) -> Any:
    if isinstance(node, dict):
        return node.get(key, default)
    return getattr(node, key, default)


def _field(event: Any, *names: str) -> Any:
    """Pull the first present field off a RawEvent model / dict / payload."""
    for name in names:
        if isinstance(event, dict):
            if event.get(name) is not None:
                return event[name]
            payload = event.get("payload") or {}
            if isinstance(payload, dict) and payload.get(name) is not None:
                return payload[name]
        else:
            val = getattr(event, name, None)
            if val is not None:
                return val
            payload = getattr(event, "payload", None) or {}
            if isinstance(payload, dict) and payload.get(name) is not None:
                return payload[name]
    return None


def resolve_tier(source: str | None, domain: str | None, policy: Any) -> tuple[str | None, str]:
    """Return ``(tier_name_or_None, matched_by)``."""
    cfg = _cfg(policy)
    domain_tiers = _get(cfg, "domain_tiers", {}) or {}
    source_tiers = _get(cfg, "source_tiers", {}) or {}

    if domain:
        hit = _suffix_lookup(domain, domain_tiers)
        if hit:
            return hit[1], f"domain:{hit[0]}"

    if source:
        key = _norm_source_key(source)
        if key in source_tiers:
            return source_tiers[key], f"source:{key}"
        # substring fallback: "OpenSanctions consolidated feed" -> opensanctions
        for src_key, tier in source_tiers.items():
            if src_key and src_key in key:
                return tier, f"source:{src_key}"

    return None, "unmatched"


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def score_source(raw_event: Any, policy: Any) -> CredibilityResult:
    """Score the credibility of a RawEvent's source in [0, 1].

    Unknown sources land on the configured default (0.5) with
    ``low_credibility=True`` — the flag is what Dev 3 renders in the trace, so
    a judge can see *why* a weak source dragged the confidence down.
    """
    cfg = _cfg(policy)
    tiers: dict[str, float] = dict(_get(cfg, "tiers", {}) or {})
    default = float(_get(cfg, "default", 0.5))
    low_threshold = float(_get(cfg, "low_credibility_threshold", 0.5))
    heur = _get(cfg, "heuristics", {}) or {}

    source = str(_field(raw_event, "source", "source_name", "adapter") or "unknown")
    url = _field(raw_event, "url", "source_url", "link")
    domain = extract_domain(url) or extract_domain(source)

    tier, matched_by = resolve_tier(source, domain, policy)

    if tier is not None and tier in tiers:
        base = float(tiers[tier])
        tier_name = tier
    else:
        base = default
        tier_name = "unknown"
        matched_by = "default"

    # --- heuristics -------------------------------------------------------- #
    adjustments: list[dict[str, Any]] = []
    score = base

    author = _field(raw_event, "author", "byline")
    no_author_penalty = float(_get(heur, "no_author_penalty", 0.0) or 0.0)
    if tier_name not in ("official_list", "inject") and not author and no_author_penalty:
        score -= no_author_penalty
        adjustments.append({"rule": "no_author", "delta": -no_author_penalty})

    text = " ".join(
        str(_field(raw_event, f) or "")
        for f in ("title", "headline", "content", "text", "summary", "snippet")
    ).lower()
    markers = [str(m).lower() for m in (_get(heur, "opinion_markers", []) or [])]
    opinion_penalty = float(_get(heur, "opinion_marker_penalty", 0.0) or 0.0)
    hits = [m for m in markers if m in text]
    if hits and opinion_penalty and tier_name != "official_list":
        score -= opinion_penalty
        adjustments.append(
            {"rule": "opinion_markers", "delta": -opinion_penalty, "matched": hits}
        )

    https_bonus = float(_get(heur, "https_bonus", 0.0) or 0.0)
    if https_bonus and isinstance(url, str) and url.lower().startswith("https://"):
        score += https_bonus
        adjustments.append({"rule": "https", "delta": https_bonus})

    score = max(0.0, min(1.0, round(score, 4)))
    low_credibility = tier_name == "unknown" or score <= low_threshold

    return CredibilityResult(
        credibility=score,
        tier=tier_name,
        source=source,
        domain=domain,
        low_credibility=low_credibility,
        breakdown={
            "source": source,
            "domain": domain,
            "tier": tier_name,
            "matched_by": matched_by,
            "base_credibility": base,
            "adjustments": adjustments,
            "credibility": score,
            "low_credibility": low_credibility,
        },
    )