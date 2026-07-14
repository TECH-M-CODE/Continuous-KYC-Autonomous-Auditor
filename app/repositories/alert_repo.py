from typing import List
from sqlalchemy.orm import Session
from app.models.events import Alert

class AlertRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, alert: Alert) -> Alert:
        self.session.add(alert)
        return alert

    def get(self, alert_id: str) -> Alert:
        return self.session.query(Alert).filter(Alert.id == alert_id).first()

    def list(self, band: str = None, status: str = None) -> List[Alert]:
        query = self.session.query(Alert)
        if band is not None:
            # support both lower/upper case as check constraint permits both
            query = query.filter(Alert.band.in_([band.lower(), band.upper()]))
        if status is not None:
            query = query.filter(Alert.status == status)
        return query.all()
