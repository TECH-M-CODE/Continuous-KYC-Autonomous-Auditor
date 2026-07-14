from typing import List
from sqlalchemy.orm import Session
from app.models.events import RawEvent

class RawEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, event: RawEvent) -> RawEvent:
        self.session.add(event)
        return event

    def get(self, event_id: str) -> RawEvent:
        return self.session.query(RawEvent).filter(RawEvent.id == event_id).first()

    def list(self, processed: bool = None, status: str = None) -> List[RawEvent]:
        query = self.session.query(RawEvent)
        if processed is not None:
            query = query.filter(RawEvent.processed == processed)
        if status is not None:
            query = query.filter(RawEvent.status == status)
        return query.all()

    def get_unprocessed(self, limit: int = 50) -> List[RawEvent]:
        return (
            self.session.query(RawEvent)
            .filter(RawEvent.processed == False)
            .order_by(RawEvent.occurred_at.asc())
            .limit(limit)
            .all()
        )

    def exists_by_hash(self, content_hash: str) -> bool:
        return (
            self.session.query(RawEvent)
            .filter(RawEvent.content_hash == content_hash)
            .first()
        ) is not None
