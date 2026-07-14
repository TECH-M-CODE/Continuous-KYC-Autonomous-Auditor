from typing import List
from sqlalchemy.orm import Session
from app.models.sanctions import SanctionsCache

class SanctionsRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, sanction: SanctionsCache) -> SanctionsCache:
        self.session.add(sanction)
        return sanction

    def get(self, sanction_id: str) -> SanctionsCache:
        return self.session.query(SanctionsCache).filter(SanctionsCache.id == sanction_id).first()

    def list(self, active: bool = None, name_normalized: str = None) -> List[SanctionsCache]:
        query = self.session.query(SanctionsCache)
        if active is not None:
            query = query.filter(SanctionsCache.active == active)
        if name_normalized is not None:
            query = query.filter(SanctionsCache.name_normalized == name_normalized)
        return query.all()
