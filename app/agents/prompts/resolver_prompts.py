"""Prompt builder for the Resolver node.

The resolver determines whether a fuzzy name match is a genuine identity
hit or a false positive. The LLM returns a structured verdict that is
blended with the deterministic confidence score (60% LLM, 40% deterministic).

Expected response schema: ResolverVerdict
    {
        "match": true/false,
        "confidence": 0.93,          // [0,1] how confident the LLM is
        "reasoning": "..."            // 1-2 sentences for the audit trace
    }
"""

from __future__ import annotations


def build_resolver_prompt(
    entity_name: str,
    entity_jurisdiction: str | None,
    screening_matches: list[dict],
    event_text: str,
    event_source: str,
    news_context: dict | None = None,
) -> str:
    """Construct the resolver prompt from runtime context."""
    matches_block = "\n".join(
        f"  - Match #{i + 1}: '{m.get('matched_name', '?')}' "
        f"(score {m.get('score', 0):.0f}/100, "
        f"source: {m.get('source', 'unknown')}, "
        f"list: {m.get('list_source', 'n/a')})"
        for i, m in enumerate(screening_matches[:5])  # cap at 5 to fit context
    )
    if not matches_block:
        matches_block = "  (no matches)"

    news_block = ""
    if news_context:
        cred = news_context.get("source_credibility", 0.0)
        flags = news_context.get("risk_flags", [])
        news_block = f"\nLIVE NEWS INTELLIGENCE:\n  Source Credibility: {cred}/100\n  Risk Flags: {', '.join(flags) if flags else 'None'}\n"

    return f"""You are a KYC compliance analyst reviewing a potential sanctions/watchlist match.

ENTITY UNDER REVIEW:
  Name: {entity_name}
  Jurisdiction: {entity_jurisdiction or "Unknown"}

FUZZY SCREENING MATCHES FOUND:
{matches_block}

SOURCE EVENT:
  Source: {event_source}
  Text: {event_text[:1000]}{news_block}

TASK:
Determine whether these screening matches represent a GENUINE identity match or a FALSE POSITIVE.

Consider:
- Name similarity vs. identical names
- Jurisdiction consistency
- Context from the event text (does it mention this entity or coincidence?)
- Whether partial-name matches are meaningful in context
- The credibility of the live news source (high credibility should increase confidence in true positives if context aligns)

Respond with ONLY this JSON (no markdown, no explanation outside the JSON):
{{
    "match": true or false,
    "confidence": <float 0.0 to 1.0 indicating your confidence in this verdict>,
    "reasoning": "<1-2 sentence explanation for the compliance audit trail>"
}}"""
