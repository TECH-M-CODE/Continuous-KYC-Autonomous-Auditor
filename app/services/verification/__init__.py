"""
app/services/verification/__init__.py

Verification Layer — Dev 2, Sprint 2.

Public surface:

    score_source(raw_event, policy)            -> CredibilityResult
    corroborate(event, uow, policy)            -> CorroborationResult
    compute_confidence(...)                    -> ConfidenceResult
    to_band(confidence, policy)                -> "dismiss" | "review" | "proceed"
    verify(event, match_score, uow, policy)    -> VerificationOutcome   (facade)

``verify()`` is the one call Dev 3's ``traced_pipeline`` makes. It returns all
three breakdown dicts so the TraceBuilder can emit a ``verify`` node without
reaching into this package's internals.
"""

from __future__ import annotations

from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict

from app.schemas.verification import (
    ConfidenceBand,
    ConfidenceResult,
    CorroborationResult,
    CredibilityResult,
)
from app.services.verification.confidence import compute_confidence, to_band
from app.services.verification.credibility import score_source
from app.services.verification.fact_check import corroborate

__all__ = [
    "score_source",
    "corroborate",
    "compute_confidence",
    "to_band",
    "verify",
    "VerificationOutcome",
    "CredibilityResult",
    "CorroborationResult",
    "ConfidenceResult",
    "ConfidenceBand",
]


class VerificationOutcome(BaseModel):
    """Everything the verification layer knows about one event."""

    model_config = ConfigDict(frozen=True)

    credibility: CredibilityResult
    corroboration: CorroborationResult
    confidence: ConfidenceResult

    @property
    def band(self) -> ConfidenceBand:
        return self.confidence.band

    @property
    def score(self) -> float:
        return self.confidence.confidence

    def trace_values(self) -> dict[str, Any]:
        """Machine-readable payload for Dev 3's ``TraceNode.values``."""
        return {
            **self.confidence.breakdown,
            "credibility_breakdown": self.credibility.breakdown,
            "corroboration_breakdown": self.corroboration.breakdown,
        }

    def trace_label(self) -> str:
        return self.confidence.label

    def trace_detail(self) -> str:
        """Human sentence for ``TraceNode.detail`` (template only, no LLM)."""
        b = self.confidence.breakdown
        parts = [
            f"Fuzzy match {b['match_score']:.0f} (normalized {b['normalized_match']:.2f})",
            f"× source credibility {b['credibility']:.2f} ({self.credibility.tier})",
        ]
        n = self.corroboration.corroborating_count
        if n:
            names = ", ".join(s.source for s in self.corroboration.sources[:3])
            parts.append(
                f"+ corroboration {b['corroboration_boost']:.2f} "
                f"({n} distinct source{'' if n == 1 else 's'}: {names})"
            )
        else:
            parts.append("+ corroboration 0.00 (uncorroborated)")

        sentence = " ".join(parts) + f" = confidence {self.score:.2f} → {self.band}."
        if self.confidence.ceiling_applied:
            sentence += (
                f" LLM degraded — capped at {b['degraded_ceiling']:.2f} "
                f"(was {b['pre_ceiling_confidence']:.2f}); routed to human review."
            )
        if self.credibility.low_credibility:
            sentence += " Low-credibility source flagged."
        return sentence


def verify(
    event: Any,
    match_score: float,
    policy: Any,
    uow: Any | None = None,
    *,
    candidates: Sequence[Any] | None = None,
    llm_verdict_confidence: float | None = None,
    degraded: bool = False,
) -> VerificationOutcome:
    """Run the full verification layer over one screened event.

    Sprint 2: ``llm_verdict_confidence`` stays None — deterministic only.
    Sprint 3: the Resolver passes its verdict confidence and ``degraded`` from
    the LLM Gateway. Nothing else in this package changes.
    """
    cred = score_source(event, policy)
    corr = corroborate(event, uow=uow, policy=policy, candidates=candidates)
    conf = compute_confidence(
        match_score=match_score,
        credibility=cred.credibility,
        corroboration=corr,
        policy=policy,
        llm_verdict_confidence=llm_verdict_confidence,
        degraded=degraded,
    )
    return VerificationOutcome(credibility=cred, corroboration=corr, confidence=conf)