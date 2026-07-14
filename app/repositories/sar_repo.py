from typing import List
from sqlalchemy.orm import Session
from app.models.sar import SARDraft

class SARRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, sar: SARDraft) -> SARDraft:
        self.session.add(sar)
        return sar

    def get(self, sar_id: str) -> SARDraft:
        return self.session.query(SARDraft).filter(SARDraft.id == sar_id).first()

    def list(self, entity_id: str = None, status: str = None) -> List[SARDraft]:
        query = self.session.query(SARDraft)
        if entity_id is not None:
            query = query.filter(SARDraft.entity_id == entity_id)
        if status is not None:
            query = query.filter(SARDraft.status == status)
        return query.all()
