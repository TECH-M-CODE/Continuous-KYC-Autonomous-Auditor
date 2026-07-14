"""Entities router: Sprint 1 returns hardcoded data matching docs/api_contract.md #2."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.entities import (
    DecisionEdgeDTO,
    DecisionNodeDTO,
    EntityDetailDTO,
    EntityGraphDTO,
    EntitySummaryDTO,
    PersonDTO,
    RiskEventDTO,
)

router = APIRouter(prefix="/entities", tags=["entities"])

_MOCK_ENTITIES: dict[str, EntityDetailDTO] = {
    "entity-1": EntityDetailDTO(
        id="entity-1",
        name="Acme Import Export Ltd",
        type="COMPANY",
        risk_score=78.5,
        risk_band="HIGH",
        jurisdiction="Cyprus",
        peps=[
            PersonDTO(
                id="person-1",
                full_name="Viktor Petrov",
                role="DIRECTOR",
                is_pep=True,
                nationality="Russia",
                risk_score=91.0,
                risk_band="CRITICAL",
            )
        ],
        recent_events=[
            RiskEventDTO(
                id="event-1",
                event_category="ADVERSE_MEDIA",
                severity="HIGH",
                score_delta=15.0,
                reasoning="Entity named in adverse media report regarding sanctioned counterparties.",
                created_at="2026-07-10T09:30:00Z",
            ),
            RiskEventDTO(
                id="event-2",
                event_category="PEP_UPDATE",
                severity="CRITICAL",
                score_delta=25.0,
                reasoning="Linked director confirmed as Politically Exposed Person.",
                created_at="2026-07-12T14:00:00Z",
            ),
        ],
    ),
    "entity-2": EntityDetailDTO(
        id="entity-2",
        name="Globex Trading Co",
        type="COMPANY",
        risk_score=12.0,
        risk_band="LOW",
        jurisdiction="Singapore",
        peps=[],
        recent_events=[],
    ),
    "entity-3": EntityDetailDTO(
        id="entity-3",
        name="Elena Kowalski",
        type="PERSON",
        risk_score=44.0,
        risk_band="MEDIUM",
        jurisdiction="Poland",
        peps=[],
        recent_events=[
            RiskEventDTO(
                id="event-3",
                event_category="TRANSACTION",
                severity="MEDIUM",
                score_delta=8.0,
                reasoning="Unusual transaction velocity detected against baseline.",
                created_at="2026-07-13T11:15:00Z",
            )
        ],
    ),
}

_MOCK_GRAPHS: dict[str, EntityGraphDTO] = {
    "entity-1": EntityGraphDTO(
        nodes=[
            DecisionNodeDTO(
                id="node-1",
                type="news",
                data={"label": "Adverse media detected", "date": "2026-07-10T09:30:00Z"},
                position={"x": 0, "y": 0},
            ),
            DecisionNodeDTO(
                id="node-2",
                type="match",
                data={"label": "Fuzzy match: Viktor Petrov (PEP list)", "score_change": 25.0, "date": "2026-07-12T14:00:00Z"},
                position={"x": 250, "y": 0},
            ),
            DecisionNodeDTO(
                id="node-3",
                type="policy",
                data={"label": "Risk band escalated to HIGH", "score_change": 40.0, "date": "2026-07-12T14:05:00Z"},
                position={"x": 500, "y": 0},
            ),
        ],
        edges=[
            DecisionEdgeDTO(id="edge-1", source="node-1", target="node-2", animated=True),
            DecisionEdgeDTO(id="edge-2", source="node-2", target="node-3", animated=True, label="score +40"),
        ],
    ),
}


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


@router.get("", response_model=APIResponse[PaginatedData[EntitySummaryDTO]])
async def list_entities(
    pagination: PaginationParams = Depends(pagination_params),
    risk_band: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[EntitySummaryDTO]]:
    entities = list(_MOCK_ENTITIES.values())

    if risk_band:
        entities = [e for e in entities if e.risk_band == risk_band.upper()]
    if search:
        entities = [e for e in entities if search.lower() in e.name.lower()]

    total = len(entities)
    start = (pagination.page - 1) * pagination.limit
    page_items = entities[start : start + pagination.limit]

    summaries = [
        EntitySummaryDTO(id=e.id, name=e.name, type=e.type, risk_score=e.risk_score, risk_band=e.risk_band)
        for e in page_items
    ]
    return success_response(paginate(summaries, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/{entity_id}", response_model=APIResponse[EntityDetailDTO])
async def get_entity(entity_id: str, request: Request):
    entity = _MOCK_ENTITIES.get(entity_id)
    if entity is None:
        return _not_found(request, entity_id)
    return success_response(entity)


@router.get("/{entity_id}/graph", response_model=APIResponse[EntityGraphDTO])
async def get_entity_graph(entity_id: str, request: Request):
    graph = _MOCK_GRAPHS.get(entity_id)
    if graph is None:
        return _not_found(request, entity_id)
    return success_response(graph)
