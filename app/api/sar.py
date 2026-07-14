"""SAR router: Sprint 1 returns hardcoded data matching docs/api_contract.md #4."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.sar import (
    CitationDTO,
    SARDecisionRequest,
    SARDetailDTO,
    SARSummaryDTO,
    SARUpdateRequest,
    SARVersionDTO,
)

router = APIRouter(prefix="/sars", tags=["sars"])

# Internal mock records carry fields (entity_name, comments) alongside the DTO-shaped data.
_MOCK_SARS: dict[str, dict] = {
    "sar-1": {
        "id": "sar-1",
        "alert_id": "alert-1",
        "entity_name": "Acme Import Export Ltd",
        "version": 1,
        "status": "PENDING_APPROVAL",
        "narrative": (
            "Acme Import Export Ltd's director, Viktor Petrov, was identified as a Politically Exposed "
            "Person following a fuzzy match against the EU sanctions PEP list. Adverse media corroborates "
            "involvement in a shell company network under investigation."
        ),
        "citations": [
            CitationDTO(source="OpenSanctions PEP List", context="Fuzzy match confidence 0.88 on 'Petrov, V.'"),
            CitationDTO(source="Reuters", context="Investigation into shell company networks, published 2026-07-10."),
        ],
        "previous_versions": [],
        "created_at": "2026-07-12T15:00:00Z",
    },
    "sar-2": {
        "id": "sar-2",
        "alert_id": "alert-3",
        "entity_name": "Elena Kowalski",
        "version": 1,
        "status": "APPROVED",
        "narrative": (
            "Elena Kowalski's account exhibited transaction velocity 3x above baseline over a 24h window. "
            "Review found no adverse media or watchlist exposure; pattern consistent with legitimate business activity."
        ),
        "citations": [
            CitationDTO(source="Internal Transaction Monitor", context="6 cross-border transfers within 24h."),
        ],
        "previous_versions": [],
        "created_at": "2026-07-13T12:00:00Z",
    },
}

_DECISION_TO_STATUS = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}


def _not_found(request: Request, sar_id: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"SAR '{sar_id}' not found.",
            "data": None,
            "trace_id": trace_id,
            "error_code": "ERR_SAR_NOT_FOUND",
        },
    )


def _to_detail(record: dict) -> SARDetailDTO:
    return SARDetailDTO(
        id=record["id"],
        alert_id=record["alert_id"],
        version=record["version"],
        status=record["status"],
        narrative=record["narrative"],
        citations=record["citations"],
        previous_versions=record["previous_versions"],
    )


def _to_summary(record: dict) -> SARSummaryDTO:
    return SARSummaryDTO(
        id=record["id"],
        alert_id=record["alert_id"],
        entity_name=record["entity_name"],
        version=record["version"],
        status=record["status"],
        created_at=record["created_at"],
    )


@router.get("", response_model=APIResponse[PaginatedData[SARSummaryDTO]])
async def list_sars(
    pagination: PaginationParams = Depends(pagination_params),
    status: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[SARSummaryDTO]]:
    records = list(_MOCK_SARS.values())

    if status:
        records = [r for r in records if r["status"] == status.upper()]

    total = len(records)
    start = (pagination.page - 1) * pagination.limit
    page_items = records[start : start + pagination.limit]

    summaries = [_to_summary(r) for r in page_items]
    return success_response(paginate(summaries, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/{sar_id}", response_model=APIResponse[SARDetailDTO])
async def get_sar(sar_id: str, request: Request):
    record = _MOCK_SARS.get(sar_id)
    if record is None:
        return _not_found(request, sar_id)
    return success_response(_to_detail(record))


@router.put("/{sar_id}", response_model=APIResponse[SARDetailDTO])
async def update_sar(sar_id: str, body: SARUpdateRequest, request: Request):
    record = _MOCK_SARS.get(sar_id)
    if record is None:
        return _not_found(request, sar_id)

    record["previous_versions"].append(
        SARVersionDTO(
            version=record["version"],
            narrative=record["narrative"],
            status=record["status"],
            created_at=record["created_at"],
        )
    )
    record["version"] += 1
    record["narrative"] = body.narrative
    record["citations"] = body.citations
    record["status"] = "DRAFT"
    record["created_at"] = datetime.now(timezone.utc).isoformat()

    return success_response(_to_detail(record), message="SAR draft updated to a new version.")


@router.post("/{sar_id}/decision", response_model=APIResponse[SARDetailDTO])
async def decide_sar(sar_id: str, body: SARDecisionRequest, request: Request):
    record = _MOCK_SARS.get(sar_id)
    if record is None:
        return _not_found(request, sar_id)

    record["status"] = _DECISION_TO_STATUS[body.decision]
    record["comments"] = body.comments
    return success_response(_to_detail(record), message=f"SAR decision recorded: {body.decision}.")
