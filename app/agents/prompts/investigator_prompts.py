"""Prompt builder for the Investigator node.

The investigator classifies the event type and extracts a severity signal.
This drives which ``policy.yaml`` weight is used in ``compute_delta()``.

Expected response schema: ClassifyEventResult
    {
        "event_type": "sanctions_hit",  // one of the policy.yaml weight keys
        "severity": 0.85,               // [0,1] event severity
        "evidence_summary": "..."       // 1-2 sentences for the investigation
    }
"""

from __future__ import annotations

# Valid event_type values must match policy.yaml ``weights`` keys.
KNOWN_EVENT_TYPES = [
    "sanctions_hit",
    "pep_flag",
    "adverse_media",
    "adverse_media_fraud",
    "transaction_anomaly",
    "fatf_country_flag",
    "watchlist_addition",
    "structuring_detected",
]


def build_investigator_prompt(
    entity_name: str,
    event_type_hint: str,
    event_text: str,
    event_source: str,
    screening_matches: list[dict],
) -> str:
    """Construct the investigator / classification prompt."""
    known_types_str = ", ".join(f'"{t}"' for t in KNOWN_EVENT_TYPES)
    match_context = (
        f"Top match: '{screening_matches[0].get('matched_name', '?')}' "
        f"(score {screening_matches[0].get('score', 0):.0f}/100)"
        if screening_matches
        else "No direct watchlist match"
    )

    return f"""You are a KYC compliance analyst classifying a risk event for entity "{entity_name}".

EVENT DETAILS:
  Source: {event_source}
  Event type hint: {event_type_hint or "unknown"}
  Screening context: {match_context}
  Text: {event_text[:1200]}

TASK:
1. Classify the event into one of these types: {known_types_str}
   - Choose the MOST specific type that fits. If the text describes a sanctions match, use "sanctions_hit".
   - If fraud/money-laundering media, use "adverse_media_fraud". If general negative press, use "adverse_media".
2. Assess the severity on a scale 0.0–1.0:
   - 1.0 = confirmed sanction, major fraud conviction
   - 0.7–0.9 = strong adverse media, PEP confirmed
   - 0.4–0.6 = unconfirmed allegations, minor anomaly
   - 0.1–0.3 = weak signal, likely noise
3. Summarise the key investigative finding in 1-2 sentences.

Respond with ONLY this JSON:
{{
    "event_type": "<one of the types listed above>",
    "severity": <float 0.0 to 1.0>,
    "evidence_summary": "<1-2 sentence summary of the key finding>"
}}"""
