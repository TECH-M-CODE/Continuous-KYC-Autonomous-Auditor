import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import uuid
from datetime import datetime, timezone
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.models.events import RawEvent
from app.models.base import Base

def trigger_test_event():
    engine = create_engine("sqlite:///./data/sentinelai.db")
    Session = sessionmaker(bind=engine)
    session = Session()

    event_id = str(uuid.uuid4())
    content = {
        "title": "New information regarding Knoedler & Company",
        "text": "Recent news has surfaced regarding Knoedler & Company, bringing up past issues.",
        "source": "Manual Trigger",
        "source_url": "https://example.com/knoedler",
        "entity_hint": "Knoedler & Company"
    }

    raw_event = RawEvent(
        id=event_id,
        feed_id="MANUAL_TEST",
        source_id="test-001",
        content=json.dumps(content),
        processed=False,
        ingested_at=datetime.now(timezone.utc),
        status="PENDING"
    )

    session.add(raw_event)
    session.commit()
    print(f"Triggered test event {event_id} for Knoedler & Company")

if __name__ == "__main__":
    trigger_test_event()
