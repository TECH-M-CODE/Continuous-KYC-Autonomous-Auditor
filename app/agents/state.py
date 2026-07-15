"""AuditorState — the single shared TypedDict threaded through every LangGraph node.

Design rules:
* Every field that a node reads MUST be present (possibly None) before that
  node runs.  Nodes only *write* fields they produce — they never mutate
  upstream fields.
* ``trace`` is a ``TraceBuilder`` instance, not a serialized ``DecisionTrace``.
  Serialization happens once, in the reporter node, just before the Alert is
  persisted.
* ``error`` is set by any node that encounters an unrecoverable failure.  The
  supervisor routes to END on non-None error, leaving the RawEvent unprocessed
  so Loop B retries it next cycle.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict

from app.services.explainability.trace import TraceBuilder


class AuditorState(TypedDict, total=False):
    # ── Source event ──────────────────────────────────────────────────────────
    event_id: str                        # RawEvent.id
    event_raw: dict[str, Any]            # parsed JSON from RawEvent.content

    # ── News enrichment (news_agent node) ─────────────────────────────────────
    # {source, source_url, credibility_tier, is_high_credibility, enriched_text}
    news_context: Optional[dict[str, Any]]

    # ── Entity resolution (entity_agent node) ─────────────────────────────────
    entity_id: Optional[str]
    entity_name: Optional[str]
    entity_risk_score: float
    entity_jurisdiction: Optional[str]
    entity_persons: list[dict[str, Any]]  # [{name, role}]

    # ── Screening (monitor node) ──────────────────────────────────────────────
    match_score: float                   # highest rapidfuzz token_set_ratio (0-100)
    screening_matches: list[dict]        # serialised ScreeningMatch objects

    # ── LLM resolver (resolver node) ──────────────────────────────────────────
    llm_verdict_confidence: Optional[float]   # [0,1] from resolver
    llm_degraded: bool                         # True → gateway exhausted

    # ── Verification combiner (resolver node) ─────────────────────────────────
    confidence: float                    # final blended confidence [0,1]
    band: str                            # "dismiss" | "review" | "proceed"

    # ── Investigator (investigator node) ──────────────────────────────────────
    event_type: Optional[str]            # classify_event result
    severity: float                      # 0.0–1.0
    jurisdiction_factor: float
    score_delta: float                   # delta applied to entity risk score
    new_risk_score: float                # entity risk score after apply_delta
    risk_band: str                       # entity risk band after apply_delta
    risk_event_id: Optional[str]         # RiskEvent.id created by apply_delta -- Alert.trigger_event_id FKs to this, not event_id
    evidence: list[dict]                 # [{source, snippet, url, relevance}]
    investigation_summary: Optional[str]

    # ── Reporter (reporter node) ───────────────────────────────────────────────
    alert_id: Optional[str]
    sar_id: Optional[str]

    # ── Trace (built throughout, finalized by reporter) ───────────────────────
    trace: TraceBuilder                  # mutable; finalized once at the end

    # ── Terminal routing ──────────────────────────────────────────────────────
    final_outcome: str    # "screened_out" | "dismissed" | "review_queued" |
                          # "alert_medium" | "alert_high" | "alert_critical"
    error: Optional[str]
