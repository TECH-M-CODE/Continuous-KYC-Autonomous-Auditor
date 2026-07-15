"""Entities router — Sprint 4: real DB reads replacing the Sprint 1 mock store."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.entities import (
    EntityDetailDTO,
    EntityGraphDTO,
    EntitySummaryDTO,
    PersonDTO,
    RiskEventDTO,
)

router = APIRouter(prefix="/entities", tags=["entities"])

# The domain model doesn't yet distinguish person-type entities (seed_entities.py
# only ever creates corporate records), so every row is reported as a COMPANY.
_ENTITY_TYPE = "COMPANY"

# Graph endpoint has no backing DB table yet (see docs discussion in alerts.py's
# DecisionTrace) — out of scope for the entities/list mock purge, left unwired.
_MOCK_GRAPHS: dict[str, EntityGraphDTO] = {}


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


@router.get("/{entity_id}", response_model=APIResponse[EntityDetailDTO])
async def get_entity(entity_id: str, request: Request):
    with UnitOfWork() as uow:
        entity = uow.entities.get(entity_id)
        if entity is None:
            return _not_found(request, entity_id)
        return success_response(_entity_to_detail(entity, uow))


@router.get("/{entity_id}/graph", response_model=APIResponse[EntityGraphDTO])
async def get_entity_graph(entity_id: str, request: Request):
    graph = _MOCK_GRAPHS.get(entity_id)
    if graph is None:
        return _not_found(request, entity_id)
    return success_response(graph)
