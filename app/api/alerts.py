"""Alerts router: Sprint 1 returns hardcoded data matching docs/api_contract.md #3."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.alerts import (
    AlertActionRequest,
    AlertDetailDTO,
    AlertSummaryDTO,
    EvidenceItemDTO,
    InvestigationDTO,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Internal mock records carry fields (entity_id, assigned_to) not exposed on the DTOs.
_MOCK_ALERTS: dict[str, dict] = {
    "alert-1": {
        "id": "alert-1",
        "entity_id": "entity-1",
        "entity_name": "Acme Import Export Ltd",
        "priority": "CRITICAL",
        "status": "OPEN",
        "assigned_to": None,
        "created_at": "2026-07-12T14:05:00Z",
        "investigation": InvestigationDTO(
            summary="Director confirmed as PEP following adverse media review; sanctions exposure suspected.",
            evidence=[
                EvidenceItemDTO(
                    source="Reuters",
                    snippet="Viktor Petrov named in ongoing investigation into shell company networks.",
                    url="https://example.com/news/petrov-investigation",
                    relevance=0.92,
                ),
                EvidenceItemDTO(
                    source="OpenSanctions",
                    snippet="Fuzzy match (0.88) against EU sanctions PEP list entry 'Petrov, V.'",
                    url=None,
                    relevance=0.88,
                ),
            ],
        ),
    },
    "alert-2": {
        "id": "alert-2",
        "entity_id": "entity-2",
        "entity_name": "Globex Trading Co",
        "priority": "LOW",
        "status": "RESOLVED",
        "assigned_to": "user-analyst-1",
        "created_at": "2026-07-05T08:00:00Z",
        "investigation": InvestigationDTO(
            summary="Minor name similarity to a delisted watchlist entry; confirmed false positive.",
            evidence=[
                EvidenceItemDTO(
                    source="OFAC SDN",
                    snippet="Delisted entry 'Globex Trading' (removed 2019) shares partial name match.",
                    url=None,
                    relevance=0.31,
                )
            ],
        ),
    },
    "alert-3": {
        "id": "alert-3",
        "entity_id": "entity-3",
        "entity_name": "Elena Kowalski",
        "priority": "MEDIUM",
        "status": "IN_PROGRESS",
        "assigned_to": "user-analyst-2",
        "created_at": "2026-07-13T11:20:00Z",
        "investigation": InvestigationDTO(
            summary="Transaction velocity spike under review; no adverse media found yet.",
            evidence=[
                EvidenceItemDTO(
                    source="Internal Transaction Monitor",
                    snippet="6 cross-border transfers within 24h, 3x above entity baseline.",
                    url=None,
                    relevance=0.75,
                )
            ],
        ),
    },
}

_ACTION_TO_STATUS = {"DISMISS": "DISMISSED", "ESCALATE": "ESCALATED", "RESOLVE": "RESOLVED"}
_ACTION_PAST_TENSE = {"DISMISS": "dismissed", "ESCALATE": "escalated", "RESOLVE": "resolved"}


def _not_found(request: Request, alert_id: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"Alert '{alert_id}' not found.",
            "data": None,
            "trace_id": trace_id,
            "error_code": "ERR_ALERT_NOT_FOUND",
        },
    )


def _to_detail(record: dict) -> AlertDetailDTO:
    return AlertDetailDTO(
        id=record["id"],
        entity_name=record["entity_name"],
        priority=record["priority"],
        status=record["status"],
        created_at=record["created_at"],
        investigation=record["investigation"],
    )


def _to_summary(record: dict) -> AlertSummaryDTO:
    return AlertSummaryDTO(
        id=record["id"],
        entity_name=record["entity_name"],
        priority=record["priority"],
        status=record["status"],
        created_at=record["created_at"],
    )


@router.get("", response_model=APIResponse[PaginatedData[AlertSummaryDTO]])
async def list_alerts(
    pagination: PaginationParams = Depends(pagination_params),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[AlertSummaryDTO]]:
    records = list(_MOCK_ALERTS.values())

    if status:
        records = [r for r in records if r["status"] == status.upper()]
    if priority:
        records = [r for r in records if r["priority"] == priority.upper()]
    if assigned_to:
        records = [r for r in records if r["assigned_to"] == assigned_to]

    total = len(records)
    start = (pagination.page - 1) * pagination.limit
    page_items = records[start : start + pagination.limit]

    summaries = [_to_summary(r) for r in page_items]
    return success_response(paginate(summaries, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/{alert_id}", response_model=APIResponse[AlertDetailDTO])
async def get_alert(alert_id: str, request: Request):
    record = _MOCK_ALERTS.get(alert_id)
    if record is None:
        return _not_found(request, alert_id)
    return success_response(_to_detail(record))


@router.patch("/{alert_id}/action", response_model=APIResponse[AlertDetailDTO])
async def act_on_alert(alert_id: str, body: AlertActionRequest, request: Request):
    record = _MOCK_ALERTS.get(alert_id)
    if record is None:
        return _not_found(request, alert_id)

    record["status"] = _ACTION_TO_STATUS[body.action]
    return success_response(_to_detail(record), message=f"Alert {_ACTION_PAST_TENSE[body.action]}.")
