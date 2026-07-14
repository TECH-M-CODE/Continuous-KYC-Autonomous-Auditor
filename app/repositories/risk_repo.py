from typing import List
from sqlalchemy.orm import Session
from app.models.risk import RiskEvent

class RiskEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, risk_event: RiskEvent) -> RiskEvent:
        self.session.add(risk_event)
        return risk_event

    def get(self, risk_event_id: str) -> RiskEvent:
        return self.session.query(RiskEvent).filter(RiskEvent.id == risk_event_id).first()

    def list(self, entity_id: str = None, severity: str = None) -> List[RiskEvent]:
        query = self.session.query(RiskEvent)
        if entity_id is not None:
            query = query.filter(RiskEvent.entity_id == entity_id)
        if severity is not None:
            query = query.filter(RiskEvent.severity == severity)
        return query.all()
