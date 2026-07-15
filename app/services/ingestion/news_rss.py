"""NewsRSSAdapter — continuous adverse media monitoring via public RSS feeds.

Feeds polled (all public, zero API keys required):
  - Reuters Business News
  - GDELT financial crime search (near real-time, updates every 15 min)

Each article becomes a RawEvent with event_type="adverse_media".
Loop A (APScheduler) runs this every 5 minutes.

Entity linking: events from RSS typically don't carry an entity_id.
The entity_agent node in the pipeline will fuzzy-match the article text
against known entity names in the DB to resolve the link.

To register:
    from app.services.ingestion.news_rss import NewsRSSAdapter
    registry.register(NewsRSSAdapter())   ← in app/main.py (ask Dev 4)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime

from app.services.ingestion.base import FeedAdapter, IngestedEvent

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RSS feed definitions — add/remove freely, no restarts needed (5-min cycle)
# ---------------------------------------------------------------------------
_RSS_FEEDS: list[dict] = [
    {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source": "reuters",
        "max_articles": 15,
    },
    {
        "url": (
            "https://api.gdeltproject.org/api/v2/doc/doc"
            "?query=sanctions+fraud+money+laundering+financial+crime"
            "&mode=artlist&format=rss&maxrecords=10"
        ),
        "source": "gdelt",
        "max_articles": 10,
    },
    {
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "source": "bbc_news",
        "max_articles": 15,
    },
]

_ADVERSE_KEYWORDS = frozenset({
    "sanction", "fraud", "money laundering", "aml", "kyc", "bribery",
    "corruption", "terrorism", "investigation", "arrested", "charged",
    "indicted", "penalty", "fine", "violated", "watchlist", "ofac",
    "resign", "cfo", "ceo", "executive", "whistleblower", "lawsuit",
})


def _is_adverse(text: str) -> bool:
    """Quick filter — only ingest articles that look compliance-relevant."""
    lower = text.lower()
    return any(kw in lower for kw in _ADVERSE_KEYWORDS)


def _parse_published(entry: dict) -> datetime:
    """Best-effort published date extraction."""
    if entry.get("published_parsed"):
        try:
            return datetime.fromtimestamp(mktime(entry["published_parsed"]), tz=timezone.utc)
        except (OverflowError, OSError):
            pass
    return datetime.now(timezone.utc)


class NewsRSSAdapter(FeedAdapter):
    """Continuously ingests live adverse media from RSS feeds.

    Inherits from FeedAdapter — Loop A calls .run() on the configured schedule.
    """

    name = "news_rss"
    schedule_seconds = 300  # every 5 minutes

    async def fetch(self) -> list[IngestedEvent]:
        try:
            import feedparser
        except ImportError:
            log.warning(
                "feedparser not installed — NewsRSSAdapter disabled. "
                "Run: pip install 'feedparser>=6.0'"
            )
            return []

        events: list[IngestedEvent] = []

        for feed_conf in _RSS_FEEDS:
            url = feed_conf["url"]
            source = feed_conf["source"]
            max_articles = feed_conf.get("max_articles", 10)

            try:
                feed = feedparser.parse(url)
                fetched = 0

                for entry in feed.entries:
                    if fetched >= max_articles:
                        break

                    title: str = entry.get("title", "")
                    summary: str = entry.get("summary", title)
                    link: str | None = entry.get("link")
                    combined = f"{title} {summary}"

                    # Only ingest compliance-relevant articles
                    if not _is_adverse(combined):
                        continue

                    published = _parse_published(entry)
                    tags = [t.get("term", "") for t in entry.get("tags", [])]

                    events.append(IngestedEvent(
                        event_type="adverse_media",
                        source=source,
                        title=title,
                        text=summary,
                        occurred_at=published,
                        source_url=link,
                        payload={
                            "raw_feed": source,
                            "tags": tags,
                            "article_url": link,
                            # entity_hint is intentionally absent here —
                            # entity_agent will fuzzy-match the title/text
                            # against known entities in the pipeline.
                        },
                    ))
                    fetched += 1

                log.debug("NewsRSSAdapter: %d adverse articles from %s", fetched, source)

            except Exception as exc:  # noqa: BLE001
                log.warning("NewsRSSAdapter: feed %s failed: %s", url, exc)
                continue

        log.info("NewsRSSAdapter: total fetched=%d articles", len(events))
        return events
