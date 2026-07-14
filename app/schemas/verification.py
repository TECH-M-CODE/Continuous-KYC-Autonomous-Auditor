"""
app/schemas/verification.py

Frozen output contracts for the Verification Layer (Dev 2, Sprint 2).

Discipline shared with the Scoring Engine (Dev 1): **never return a bare
float**. Every result carries a machine-readable ``breakdown`` dict that goes
verbatim into Dev 3's TraceNode.values and into the persisted audit record.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ConfidenceBand = Literal["dismiss", "review", "proceed"]


class CredibilityResult(BaseModel):
    """Output of ``credibility.score_source``."""

    model_config = ConfigDict(frozen=True)

    credibility: float = Field(..., ge=0.0, le=1.0)
    tier: str = Field(..., description="Tier name from policy, or 'unknown'.")
    source: str = Field(..., description="Raw source string off the RawEvent.")
    domain: str | None = Field(None, description="Registrable domain, if resolvable.")
    low_credibility: bool = Field(
        False,
        description="True for unknown/blog-tier sources. Surfaces in the trace.",
    )
    breakdown: dict[str, Any] = Field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"Credibility {self.credibility:.2f} ({self.tier})"


class CorroboratingSource(BaseModel):
    """One distinct source that independently reported the same entity."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    source: str
    domain: str | None = None
    published_at: Any | None = None
    name_match: float = Field(..., ge=0.0, le=100.0)
    hours_apart: float


class CorroborationResult(BaseModel):
    """Output of ``fact_check.corroborate``."""

    model_config = ConfigDict(frozen=True)

    corroborating_count: int = Field(0, ge=0)
    sources: list[CorroboratingSource] = Field(default_factory=list)
    corroboration_boost: float = Field(0.0, ge=0.0, le=1.0)
    window_hours: int = 72
    breakdown: dict[str, Any] = Field(default_factory=dict)

    @property
    def label(self) -> str:
        n = self.corroborating_count
        return f"Corroboration {n} source{'' if n == 1 else 's'} (+{self.corroboration_boost:.2f})"


class ConfidenceResult(BaseModel):
    """Output of ``confidence.compute_confidence`` — drives the 3-way branch."""

    model_config = ConfigDict(frozen=True)

    confidence: float = Field(..., ge=0.0, le=1.0)
    band: ConfidenceBand
    degraded: bool = False
    ceiling_applied: bool = Field(
        False, description="True when the degraded ceiling clamped the score down."
    )
    llm_blended: bool = Field(
        False, description="True when an LLM verdict confidence was blended in."
    )
    breakdown: dict[str, Any] = Field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"Confidence {self.confidence:.2f} → {self.band}"

    @property
    def proceed(self) -> bool:
        return self.band == "proceed"