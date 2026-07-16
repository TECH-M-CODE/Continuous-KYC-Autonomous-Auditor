"""Entities router — Sprint 4: real DB reads replacing the Sprint 1 mock store."""
from typing import Optional
import csv
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Body
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.models.entities import Entity
from app.schemas.entities import (
    DecisionEdgeDTO,
    DecisionNodeData,
    DecisionNodeDTO,
    DecisionNodePosition,
    EntityDetailDTO,
    EntityGraphDTO,
    EntitySummaryDTO,
    PersonDTO,
    RiskEventDTO,
)

router = APIRouter(prefix="/entities", tags=["entities"])


def _display_type(entity) -> str:
    """Normalize the stored entity_type to the label the UI expects.

    The dataset stores "Person" / "Organization"; the frontend switches its icon
    on the literal "Person", and shows the label verbatim otherwise.
    """
    raw = (getattr(entity, "entity_type", None) or "Organization").strip().lower()
    if raw in ("person", "individual"):
        return "Person"
    return "Company"

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
        type=_display_type(entity),
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
        type=_display_type(entity),
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

@router.get("/check-duplicate/name")
async def check_duplicate(name: str = Query(...)):
    with UnitOfWork() as uow:
        # Very simple check
        entities = uow.entities.list()
        matches = [e for e in entities if name.lower() in e.name.lower()]
        summaries = [_entity_to_summary(e) for e in matches]
    return success_response(summaries)


@router.post("/onboard")
async def onboard_customer(
    name: str = Body(...),
    type: str = Body(...),
    jurisdiction: str = Body(None),
    sector: str = Body(None),
):
    entity_id = f"ent-{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow()
    
    # 1. Insert into DB
    with UnitOfWork() as uow:
        new_entity = Entity(
            id=entity_id,
            name=name,
            entity_type=type.upper(),
            jurisdiction=jurisdiction,
            industry=sector,
            risk_score=10,
            risk_band="LOW",
            created_at=now,
            updated_at=now,
        )
        uow.entities.add(new_entity)
        uow.commit()
    
    # 2. Append to CSV
    csv_path = os.path.join("data", "kyc_profiles", "dataset_profiles.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # headers: customer_id,entity_name,entity_type,country,industry,executives,beneficial_owners,registration_country,countries_of_operation,risk_score,risk_level,adverse_media_count,financial_fraud_count,sanctions_count,regulatory_mentions,latest_incident_date,existing_alerts,risk_indicators,last_review_date,monitoring_status,kyc_status
            writer.writerow([
                entity_id, name, type.capitalize(), jurisdiction or "", sector or "", 
                "", "", jurisdiction or "", jurisdiction or "", 
                "10", "LOW", "0", "0", "0", "0", 
                "", "0", "", now.isoformat(), "Active", "Verified"
            ])
            
    return success_response({
        "id": entity_id,
        "name": name,
        "type": type,
        "risk_score": 10,
        "risk_band": "LOW"
    })

