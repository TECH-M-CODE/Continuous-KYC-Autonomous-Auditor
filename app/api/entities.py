"""Entities router — Sprint 4: real DB reads replacing the Sprint 1 mock store."""
from typing import Optional
import csv
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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

def _normalize_name(name: str) -> str:
    """Case/whitespace-insensitive key used for duplicate detection."""
    return " ".join((name or "").strip().lower().split())


def _norm_type(raw: str) -> str:
    """Frontend sends PERSON/COMPANY; the dataset stores Person/Organization."""
    return "Person" if (raw or "").strip().lower() in ("person", "individual") else "Organization"


def _match_dto(entity) -> dict:
    return {
        "id": entity.id,
        "name": entity.name,
        "type": _display_type(entity),
        "jurisdiction": entity.jurisdiction,
        "risk_score": entity.risk_score,
        "risk_band": entity.risk_band,
    }


@router.get("/check-duplicate/name")
async def check_duplicate(name: str = Query(...)):
    """Return existing records that plausibly refer to the same customer.

    Exact (normalized) name matches plus close fuzzy matches — a substring test
    alone flags every "Kim" against every other "Kim", which trains reviewers to
    click through the warning.
    """
    from rapidfuzz import fuzz

    target = _normalize_name(name)
    if not target:
        return success_response([])

    with UnitOfWork() as uow:
        matches = [
            e for e in uow.entities.list()
            if _normalize_name(e.name) == target
            or fuzz.token_sort_ratio(target, _normalize_name(e.name)) >= 88
        ]
        payload = [_match_dto(e) for e in matches]
    return success_response(payload)


class OnboardRequest(BaseModel):
    name: str
    type: str = "COMPANY"
    jurisdiction: Optional[str] = None
    sector: Optional[str] = None
    # Set once a human has looked at the possible duplicates and confirmed this
    # really is a different customer.
    confirm_distinct: bool = False


@router.post("/onboard", response_model=APIResponse[dict])
async def onboard_customer(body: OnboardRequest, request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    name = (body.name or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={
            "success": False, "message": "Customer name is required.",
            "data": None, "trace_id": trace_id, "error_code": "ERR_VALIDATION_FAILED",
        })

    entity_type = _norm_type(body.type)
    jurisdiction = (body.jurisdiction or "").strip() or None
    sector = (body.sector or "").strip() or None
    norm = _normalize_name(name)

    with UnitOfWork() as uow:
        same_name = [e for e in uow.entities.list() if _normalize_name(e.name) == norm]

        # Same name + same jurisdiction + same type is indistinguishable from the
        # existing record — refuse outright rather than fork the customer's history.
        exact = [
            e for e in same_name
            if (e.jurisdiction or "").strip().lower() == (jurisdiction or "").strip().lower()
            and (getattr(e, "entity_type", "") or "").strip().lower() == entity_type.lower()
        ]
        if exact:
            return JSONResponse(status_code=409, content={
                "success": False,
                "message": (
                    f"'{name}' already exists as {exact[0].id}"
                    + (f" in {jurisdiction}" if jurisdiction else "")
                    + ". This would create a duplicate customer record."
                ),
                "data": {"existing": [_match_dto(e) for e in exact]},
                "trace_id": trace_id,
                "error_code": "ERR_DUPLICATE_ENTITY",
            })

        # Same name but a different jurisdiction/type could legitimately be a
        # different customer — require an explicit human confirmation.
        if same_name and not body.confirm_distinct:
            return JSONResponse(status_code=409, content={
                "success": False,
                "message": f"{len(same_name)} existing record(s) share this name. Confirm this is a distinct customer.",
                "data": {"possible_duplicates": [_match_dto(e) for e in same_name]},
                "trace_id": trace_id,
                "error_code": "ERR_POSSIBLE_DUPLICATE",
            })

        entity_id = f"CUST-ONB-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        uow.entities.add(Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,   # NB: the column is `sector`, not `industry`
            jurisdiction=jurisdiction,
            sector=sector,
            risk_score=10.0,
            risk_band="LOW",
            status="ACTIVE",
            watched=False,
            created_at=now,
            updated_at=now,
        ))
        uow.commit()

    # Mirror into the seed dataset so the customer survives a reseed.
    csv_path = os.path.join("data", "kyc_profiles", "dataset_profiles.csv")
    try:
        if os.path.exists(csv_path):
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([
                    entity_id, name, entity_type, jurisdiction or "", sector or "",
                    "", "", jurisdiction or "", jurisdiction or "",
                    "10", "LOW", "0", "0", "0", "0",
                    "", "0", "", now.date().isoformat(), "Active", "Approved",
                ])
    except OSError:
        pass  # DB is the source of truth; a CSV mirror failure must not 500 the request

    return success_response(
        {"id": entity_id, "name": name, "type": _norm_type(body.type),
         "jurisdiction": jurisdiction, "risk_score": 10.0, "risk_band": "LOW"},
        message=f"{name} onboarded and added to monitoring.",
    )

