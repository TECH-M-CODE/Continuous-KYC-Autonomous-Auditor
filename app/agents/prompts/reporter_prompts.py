"""Prompt builder for the Reporter node.

The reporter synthesises a SAR (Suspicious Activity Report) narrative from
the full investigation context. Citations must reference real sources cited
in the investigation evidence.

Expected response schema: SARNarrativeResult
    {
        "narrative": "...",
        "citations": [
            {"citation": "FATF Rec. 20", "passage": "..."},
            ...
        ]
    }
"""

from __future__ import annotations


def build_reporter_prompt(
    entity_name: str,
    entity_jurisdiction: str | None,
    event_type: str,
    severity: float,
    evidence_summary: str,
    screening_matches: list[dict],
    confidence: float,
    risk_band: str,
    new_risk_score: float,
) -> str:
    """Construct the SAR narrative generation prompt."""
    match_lines = "\n".join(
        f"  - '{m.get('matched_name', '?')}' (score {m.get('score', 0):.0f}, "
        f"source: {m.get('source', '?')}, list: {m.get('list_source', 'internal')})"
        for m in screening_matches[:5]
    )
    if not match_lines:
        match_lines = "  (no direct watchlist matches)"

    return f"""You are a compliance officer drafting a Suspicious Activity Report (SAR) narrative.

SUBJECT:
  Entity name: {entity_name}
  Jurisdiction: {entity_jurisdiction or "Unknown"}

RISK ASSESSMENT:
  Event classification: {event_type}
  Severity: {severity:.2f}/1.0
  Confidence score: {confidence:.2f}/1.0
  Risk band: {risk_band}
  Updated risk score: {new_risk_score:.1f}/100

INVESTIGATION FINDINGS:
  Summary: {evidence_summary}

SCREENING MATCHES:
{match_lines}

TASK:
Draft a concise SAR narrative (3–5 sentences) suitable for regulatory filing. The narrative must:
1. State the subject entity and the nature of the suspicious activity
2. Reference the screening matches or event details that triggered the alert
3. Note the risk score and band
4. Be factual and written in the third person

Also provide 2–3 regulatory citations relevant to this scenario (e.g., FATF recommendations,
BSA requirements, GDPR Art. 30, AML directives).

Respond with ONLY this JSON:
{{
    "narrative": "<3-5 sentence SAR narrative>",
    "citations": [
        {{"citation": "<regulation name>", "passage": "<relevant passage or description>"}},
        ...
    ]
}}"""
