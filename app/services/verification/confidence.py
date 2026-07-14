"""
app/services/verification/confidence.py

The combiner — Dev 2, Sprint 2.

Produces the single number that drives the three-way branch in activity diagram
5.1:

        confidence < 0.40          -> dismiss
        0.40 <= confidence < 0.75  -> review   (human queue)
        confidence >= 0.75         -> proceed  (classify -> score -> alert)

Sprint 2 formula (no LLM anywhere in this module):

        deterministic = normalize(fuzzy_match_score) * credibility
                        + corroboration_boost                 , clamped 0-1

Sprint 3 seam — already built, do not redesign later:

        confidence = 0.6 * llm_verdict_confidence + 0.4 * deterministic

    The ``llm_verdict_confidence`` parameter is optional and defaults to None,
    so Sprint 3 changes exactly one call site (the Resolver agent) and nothing
    in here.

Degraded-LLM path: when the gateway reports ``degraded=True``, the deterministic
score stands but is capped at 0.74 — the system can never auto-proceed without
the LLM, it falls through to human review. Fail-safe by construction.
"""

from __future__ import annotations

from typing import Any, Literal

from app.schemas.verification import (
    ConfidenceBand,
    ConfidenceResult,
    CorroborationResult,
)

__all__ = ["compute_confidence", "to_band"]


def _cfg(policy: Any) -> Any:
    node = policy
    for key in ("verification", "confidence"):
        node = node.get(key) if isinstance(node, dict) else getattr(node, key)
    return node


def _c(node: Any, key: str, default: Any = None) -> Any:
    return node.get(key, default) if isinstance(node, dict) else getattr(node, key, default)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# --------------------------------------------------------------------------- #
# banding
# --------------------------------------------------------------------------- #
def to_band(confidence: float, policy: Any) -> ConfidenceBand:
    """Map a confidence in [0,1] to dismiss / review / proceed."""
    bands = _c(_cfg(policy), "bands", {}) or {}
    dismiss_below = float(_c(bands, "dismiss_below", 0.40) or 0.40)
    proceed_at = float(_c(bands, "proceed_at_or_above", 0.75) or 0.75)

    if confidence < dismiss_below:
        return "dismiss"
    if confidence >= proceed_at:
        return "proceed"
    return "review"


# --------------------------------------------------------------------------- #
# the combiner
# --------------------------------------------------------------------------- #
def compute_confidence(
    match_score: float,
    credibility: float,
    corroboration: CorroborationResult | float | None,
    policy: Any,
    *,
    llm_verdict_confidence: float | None = None,
    degraded: bool = False,
) -> ConfidenceResult:
    """Combine deterministic verification signals into one confidence + band.

    Parameters
    ----------
    match_score
        Fuzzy screening score from Dev 4's ``screening.py`` (rapidfuzz
        ``token_set_ratio``, 0-100). Values <= 1.0 are accepted as already
        normalized.
    credibility
        ``CredibilityResult.credibility`` in [0,1] — or the result object.
    corroboration
        ``CorroborationResult`` from ``fact_check.corroborate``. A bare float is
        also accepted and treated as the boost.
    policy
        Hot-reloadable policy object (Dev 1's loader).
    llm_verdict_confidence
        **Sprint 3 seam.** Resolver's LLM verdict confidence in [0,1]. When
        present it is blended: ``0.6*llm + 0.4*deterministic``. Leave as None in
        Sprint 2.
    degraded
        True when the LLM Gateway degraded (retry -> fallback -> cache all
        failed). Forces the ceiling of 0.74 so the event can only reach review,
        never auto-proceed.
    """
    cfg = _cfg(policy)
    scale = float(_c(cfg, "match_score_scale", 100.0) or 100.0)
    llm_w = float(_c(cfg, "llm_weight", 0.6) or 0.6)
    det_w = float(_c(cfg, "deterministic_weight", 0.4) or 0.4)
    ceiling = float(_c(cfg, "degraded_ceiling", 0.74) or 0.74)

    # --- normalize inputs -------------------------------------------------- #
    raw_match = float(match_score or 0.0)
    normalized_match = _clamp01(raw_match if raw_match <= 1.0 else raw_match / scale)

    cred = getattr(credibility, "credibility", credibility)
    cred = _clamp01(float(cred or 0.0))

    if isinstance(corroboration, CorroborationResult):
        boost = float(corroboration.corroboration_boost)
        corr_count = corroboration.corroborating_count
        corr_sources = [s.source for s in corroboration.sources]
    elif corroboration is None:
        boost, corr_count, corr_sources = 0.0, 0, []
    else:
        boost, corr_count, corr_sources = float(corroboration), 0, []

    # --- deterministic core ------------------------------------------------ #
    base = normalized_match * cred
    deterministic = _clamp01(base + boost)

    # --- Sprint 3 blend (inert while llm_verdict_confidence is None) -------- #
    llm_blended = llm_verdict_confidence is not None
    if llm_blended:
        llm_conf = _clamp01(float(llm_verdict_confidence))
        confidence = _clamp01(llm_w * llm_conf + det_w * deterministic)
    else:
        llm_conf = None
        confidence = deterministic

    # --- degraded ceiling (fail-safe) -------------------------------------- #
    pre_ceiling = confidence
    ceiling_applied = False
    if degraded and confidence > ceiling:
        confidence = ceiling
        ceiling_applied = True

    confidence = round(confidence, 4)
    band = to_band(confidence, policy)

    breakdown: dict[str, Any] = {
        "match_score": raw_match,
        "normalized_match": round(normalized_match, 4),
        "credibility": round(cred, 4),
        "base": round(base, 4),
        "corroboration_boost": round(boost, 4),
        "corroborating_count": corr_count,
        "corroborating_sources": corr_sources,
        "deterministic": round(deterministic, 4),
        "llm_verdict_confidence": llm_conf,
        "llm_blended": llm_blended,
        "weights": {"llm": llm_w, "deterministic": det_w} if llm_blended else None,
        "degraded": degraded,
        "degraded_ceiling": ceiling,
        "pre_ceiling_confidence": round(pre_ceiling, 4),
        "ceiling_applied": ceiling_applied,
        "confidence": confidence,
        "band": band,
        "formula": (
            "confidence = 0.6*llm + 0.4*(normalize(match) * credibility + boost)"
            if llm_blended
            else "confidence = normalize(match) * credibility + boost"
        ),
    }

    return ConfidenceResult(
        confidence=confidence,
        band=band,
        degraded=degraded,
        ceiling_applied=ceiling_applied,
        llm_blended=llm_blended,
        breakdown=breakdown,
    )