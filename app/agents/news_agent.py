"""News Agent — event context enrichment.

Responsibilities
----------------
1. Extract source metadata from event_raw (URL, source name, publication date).
2. Detect source credibility tier (high/medium/low).
3. Optionally verify the source URL is reachable (non-blocking, 3s timeout).
4. Emit an "event" trace node with source metadata.
5. Set state["news_context"] for downstream nodes (resolver prompts, reporter RAG).

Falls back gracefully if the URL is unreachable — the event still proceeds
with only the text already in event_raw. This node never blocks the pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.state import AuditorState

log = logging.getLogger(__name__)

# Sources in this set get a credibility boost in the verification layer.
_HIGH_CRED_SOURCES = frozenset({
    "reuters", "bloomberg", "ft.com", "wsj", "financial times",
    "bbc", "ap news", "associated press",
    "ofac", "fincen", "fatf", "eu", "un", "interpol",
    "sec", "fca", "ecb",
})

_MEDIUM_CRED_SOURCES = frozenset({
    "cnbc", "cnn", "nytimes", "guardian", "telegraph",
    "forbes", "economist", "politico", "axios",
    "gdelt", "rss",
})


def _classify_credibility(source: str) -> str:
    """Return 'high' | 'medium' | 'low' for the named source."""
    s = source.lower()
    if any(h in s for h in _HIGH_CRED_SOURCES):
        return "high"
    if any(m in s for m in _MEDIUM_CRED_SOURCES):
        return "medium"
    return "low"


def _try_verify_url(url: str | None) -> str:
    """Attempt a HEAD request to confirm the article URL is live.

    Returns a short status string — used only for the trace, never raises.
    """
    if not url:
        return "no_url"
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return f"live_{resp.status}"
    except Exception as exc:  # noqa: BLE001
        log.debug("news_agent: URL verify failed for %s: %s", url, exc)
        return "unreachable"


def news_agent(state: AuditorState) -> AuditorState:
    """News context enrichment node — sync, no DB access, non-blocking."""
    event_raw: dict[str, Any] = state.get("event_raw", {})
    tb = state["trace"]

    source_name: str = event_raw.get("source", "unknown")
    source_url: str | None = event_raw.get("source_url")
    event_text: str = event_raw.get("text", "")
    event_title: str = event_raw.get("title", "")

    credibility_tier = _classify_credibility(source_name)
    url_status = _try_verify_url(source_url)

    tb.add(
        kind="event",
        label=f"News source: {source_name} [{credibility_tier} credibility]",
        detail=(
            f"Title: {event_title[:120] if event_title else 'N/A'} | "
            f"Source: {source_name} | URL status: {url_status}"
        ),
        values={
            "source": source_name,
            "source_url": source_url,
            "credibility_tier": credibility_tier,
            "is_high_credibility": credibility_tier == "high",
            "text_length": len(event_text),
            "url_status": url_status,
        },
        outcome="pass",
    )

    state["news_context"] = {
        "source": source_name,
        "source_url": source_url,
        "credibility_tier": credibility_tier,
        "is_high_credibility": credibility_tier == "high",
        "enriched_text": event_text,
        "url_status": url_status,
    }
    state["trace"] = tb

    log.info(
        "news_agent: source=%s credibility=%s url=%s",
        source_name, credibility_tier, url_status,
    )
    return state
