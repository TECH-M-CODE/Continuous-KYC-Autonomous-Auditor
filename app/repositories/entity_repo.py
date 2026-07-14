from typing import List
from sqlalchemy.orm import Session
from app.models.entities import Entity

class EntityRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, entity: Entity) -> Entity:
        self.session.add(entity)
        return entity

    def get(self, entity_id: str) -> Entity:
        return self.session.query(Entity).filter(Entity.id == entity_id).first()

    def list(self, watched: bool = None, name: str = None) -> List[Entity]:
        query = self.session.query(Entity)
        if watched is not None:
            query = query.filter(Entity.watched == watched)
        if name is not None:
            query = query.filter(Entity.name.like(f"%{name}%"))
        return query.all()
