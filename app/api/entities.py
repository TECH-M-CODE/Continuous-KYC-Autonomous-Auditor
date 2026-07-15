"""Entities router — Sprint 4: real DB reads replacing the Sprint 1 mock store."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

import uuid
import json
import hashlib
from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.models.entities import Entity
from app.models.events import RawEvent
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.entities import (
    DecisionEdgeDTO,
    DecisionNodeData,
    DecisionNodeDTO,
    DecisionNodePosition,
    EntityDetailDTO,
    EntityGraphDTO,
    EntitySummaryDTO,
    EntityCreateDTO,
    PersonDTO,
    RiskEventDTO,
)
from pydantic import BaseModel

class DuplicateMatchDTO(BaseModel):
    id: str
    name: str
    type: str
    role: str
    risk_band: str
    risk_score: float

router = APIRouter(prefix="/entities", tags=["entities"])

# The domain model doesn't yet distinguish person-type entities (seed_entities.py
# only ever creates corporate records), so every row is reported as a COMPANY.
_ENTITY_TYPE = "COMPANY"

# Map a RiskEvent's category onto the frontend DecisionGraph node types.
_CATEGORY_NODE_TYPE = {
    "SANCTION": "match",
    "AUTOMATED_SCREENING": "match",
    "PROPAGATED": "match",
    "ADVERSE_MEDIA": "news",
    "PEP_UPDATE": "news",
    "TRANSACTION": "news",
}


def _build_entity_graph(entity, uow: UnitOfWork) -> EntityGraphDTO:
    """Build a decision graph (React-Flow shape) from the entity's risk history.

    Each RiskEvent becomes a node carrying its score delta and timestamp; nodes are
    chained in chronological order and terminate in a single 'policy' node that
    represents the entity's current risk posture. This is real, per-entity data —
    no fixed table is needed because the graph is derived from risk_events.
    """
    risk_events = sorted(
        uow.risk_events.list(entity_id=entity.id),
        key=lambda e: e.created_at,
    )

    nodes: list[DecisionNodeDTO] = []
    edges: list[DecisionEdgeDTO] = []

    for i, re in enumerate(risk_events):
        node_type = _CATEGORY_NODE_TYPE.get((re.event_category or "").upper(), "news")
        nodes.append(
            DecisionNodeDTO(
                id=re.id,
                type=node_type,
                data=DecisionNodeData(
                    label=(re.reasoning or re.event_category or "Risk event")[:80],
                    score_change=re.delta,
                    date=re.created_at,
                ),
                position=DecisionNodePosition(x=i * 220.0, y=(i % 2) * 120.0),
            )
        )
        if i > 0:
            prev = risk_events[i - 1]
            edges.append(
                DecisionEdgeDTO(
                    id=f"e-{prev.id}-{re.id}",
                    source=prev.id,
                    target=re.id,
                    animated=(i == len(risk_events) - 1),
                    label=f"+{re.delta:.0f}" if re.delta else None,
                )
            )

    # Terminal policy node summarising the entity's current risk band/score.
    policy_id = f"policy-{entity.id}"
    nodes.append(
        DecisionNodeDTO(
            id=policy_id,
            type="policy",
            data=DecisionNodeData(
                label=f"{entity.risk_band} risk (score {entity.risk_score:.0f})",
                score_change=None,
                date=entity.updated_at or entity.created_at,
            ),
            position=DecisionNodePosition(x=len(risk_events) * 220.0, y=60.0),
        )
    )
    if risk_events:
        last = risk_events[-1]
        edges.append(
            DecisionEdgeDTO(
                id=f"e-{last.id}-{policy_id}",
                source=last.id,
                target=policy_id,
                animated=True,
                label="current",
            )
        )

    return EntityGraphDTO(nodes=nodes, edges=edges)


def _not_found(request: Request, entity_id: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"Entity '{entity_id}' not found.",
            "data": None,
            "trace_id": trace_id,
            "error_code": "ERR_ENTITY_NOT_FOUND",
        },
    )


def _entity_to_summary(entity) -> EntitySummaryDTO:
    return EntitySummaryDTO(
        id=entity.id,
        name=entity.name,
        type=_ENTITY_TYPE,
        risk_score=entity.risk_score,
        risk_band=entity.risk_band,
    )


def _entity_to_detail(entity, uow: UnitOfWork) -> EntityDetailDTO:
    persons = [
        PersonDTO(
            id=str(p.id),
            full_name=p.person_name,
            role=p.role,
            is_pep=False,  # no per-person PEP flag in the domain model yet
            nationality=None,
            risk_score=entity.risk_score,  # individual scoring not modeled; inherit parent
            risk_band=entity.risk_band,
        )
        for p in entity.persons
    ]

    risk_events = sorted(
        uow.risk_events.list(entity_id=entity.id),
        key=lambda e: e.created_at,
        reverse=True,
    )
    recent_events = [
        RiskEventDTO(
            id=re.id,
            event_category=re.event_category or "UNKNOWN",
            severity=re.severity,
            score_delta=re.delta,
            reasoning=re.reasoning or "",
            created_at=re.created_at,
        )
        for re in risk_events
    ]

    return EntityDetailDTO(
        id=entity.id,
        name=entity.name,
        type=_ENTITY_TYPE,
        risk_score=entity.risk_score,
        risk_band=entity.risk_band,
        jurisdiction=entity.jurisdiction or "",
        peps=persons,
        recent_events=recent_events,
    )


@router.get("", response_model=APIResponse[PaginatedData[EntitySummaryDTO]])
async def list_entities(
    pagination: PaginationParams = Depends(pagination_params),
    risk_band: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[EntitySummaryDTO]]:
    with UnitOfWork() as uow:
        entities = uow.entities.list(name=search or None)

        # risk_band isn't natively supported by the repo; filter in-memory like alerts.py does for priority.
        if risk_band:
            entities = [e for e in entities if e.risk_band == risk_band.upper()]

        total = len(entities)
        start = (pagination.page - 1) * pagination.limit
        page_items = entities[start: start + pagination.limit]
        summaries = [_entity_to_summary(e) for e in page_items]

    return success_response(paginate(summaries, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/check-duplicate", response_model=APIResponse[list[DuplicateMatchDTO]])
async def check_duplicate(name: str = Query(...)):
    name_lower = name.lower()
    matches = []
    
    with UnitOfWork() as uow:
        # 1. Check primary entities
        entities = uow.session.query(Entity).filter(
            Entity.name.ilike(f"%{name_lower}%")
        ).all()
        for e in entities:
            matches.append(DuplicateMatchDTO(
                id=e.id,
                name=e.name,
                type="COMPANY",
                role="Primary Entity",
                risk_band=e.risk_band,
                risk_score=e.risk_score
            ))
            
        # 2. Check persons
        from app.models.entities import EntityPerson
        persons = uow.session.query(EntityPerson).filter(
            EntityPerson.person_name.ilike(f"%{name_lower}%")
        ).all()
        for p in persons:
            e = p.entity
            if e:
                matches.append(DuplicateMatchDTO(
                    id=e.id,
                    name=p.person_name,
                    type="PERSON",
                    role=f"{p.role} at {e.name}",
                    risk_band=e.risk_band,
                    risk_score=e.risk_score
                ))
                
    return success_response(matches)


@router.get("/{entity_id}", response_model=APIResponse[EntityDetailDTO])
async def get_entity(entity_id: str, request: Request):
    with UnitOfWork() as uow:
        entity = uow.entities.get(entity_id)
        if entity is None:
            return _not_found(request, entity_id)
        return success_response(_entity_to_detail(entity, uow))


@router.get("/{entity_id}/graph", response_model=APIResponse[EntityGraphDTO])
async def get_entity_graph(entity_id: str, request: Request):
    with UnitOfWork() as uow:
        entity = uow.entities.get(entity_id)
        if entity is None:
            return _not_found(request, entity_id)
        return success_response(_build_entity_graph(entity, uow))


@router.post("", response_model=APIResponse[EntitySummaryDTO])
async def create_entity(data: EntityCreateDTO):
    with UnitOfWork() as uow:
        entity_id = f"C_{uuid.uuid4().hex[:8]}"
        entity = Entity(
            id=entity_id,
            name=data.name,
            jurisdiction=data.jurisdiction,
            sector=data.sector,
            risk_score=0.0,
            risk_band="LOW",
            status="ACTIVE",
            watched=True
        )
        uow.entities.add(entity)

        # Trigger instant sanctions scan
        content = json.dumps({
            "event_type": "NEW_CUSTOMER_SCAN",
            "source": "manual_entry",
            "entity_hint": entity_id,
            "entity_name": data.name,
            "text": f"New customer {data.name} added. Immediate sanctions scan required."
        })
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        raw_event = RawEvent(
            id=f"E_{uuid.uuid4().hex[:8]}",
            content_hash=content_hash,
            content=content,
            processed=False,
            status="PENDING"
        )
        uow.events.add(raw_event)
        
        uow.commit()
        return success_response(_entity_to_summary(entity))
