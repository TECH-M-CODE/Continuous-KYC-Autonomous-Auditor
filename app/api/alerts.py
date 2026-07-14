"""Alerts router — Sprint 3: real DB reads replacing the Sprint 1 mock store."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.alerts import (
    AlertActionRequest,
    AlertDetailDTO,
    AlertSummaryDTO,
    EvidenceItemDTO,
    InvestigationDTO,
)
from app.schemas.traces import DecisionTrace

router = APIRouter(prefix="/alerts", tags=["alerts"])

_ACTION_TO_STATUS = {"DISMISS": "DISMISSED", "ESCALATE": "ESCALATED", "RESOLVE": "RESOLVED"}


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


def _parse_trace(trace_json: str | None) -> Optional[DecisionTrace]:
    """Deserialise the stored DecisionTrace JSON, returning None on any error."""
    if not trace_json:
        return None
    try:
        return DecisionTrace.model_validate_json(trace_json)
    except Exception:
        return None


def _alert_to_summary(alert, entity_name: str) -> AlertSummaryDTO:
    return AlertSummaryDTO(
        id=alert.id,
        entity_name=entity_name,
        priority=alert.priority.upper(),
        status=alert.status.upper(),
        created_at=alert.created_at,
    )


def _alert_to_detail(alert, entity_name: str) -> AlertDetailDTO:
    # Build an InvestigationDTO from the stored DecisionTrace (best-effort)
    trace = _parse_trace(alert.trace)
    if trace:
        summary_text = (
            f"Automated investigation: {trace.final_outcome.replace('_', ' ').title()}. "
            f"Trace contains {len(trace.nodes)} decision nodes."
        )
        evidence = [
            EvidenceItemDTO(
                source=node.values.get("source", "AI Agent"),
                snippet=node.detail,
                url=node.values.get("source_url"),
                relevance=min(1.0, float(node.values.get("top_score", node.values.get("confidence", 0.75)) or 0) / 100.0
                            if node.values.get("top_score") is not None
                            else float(node.values.get("confidence", 0.75) or 0.75)),
            )
            for node in trace.nodes
            if node.kind in ("screen", "resolve", "classify")
        ]
    else:
        summary_text = "Investigation data not yet available."
        evidence = []

    return AlertDetailDTO(
        id=alert.id,
        entity_name=entity_name,
        priority=alert.priority.upper(),
        status=alert.status.upper(),
        created_at=alert.created_at,
        investigation=InvestigationDTO(summary=summary_text, evidence=evidence),
        trace=trace,
    )


@router.get("", response_model=APIResponse[PaginatedData[AlertSummaryDTO]])
async def list_alerts(
    pagination: PaginationParams = Depends(pagination_params),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[AlertSummaryDTO]]:
    with UnitOfWork() as uow:
        alerts = uow.alerts.list(
            band=None,
            status=status.upper() if status else None,
        )
        # Filter priority in-memory (alert_repo doesn't support it natively)
        if priority:
            alerts = [a for a in alerts if a.priority.upper() == priority.upper()]
        if assigned_to:
            alerts = [a for a in alerts if a.assigned_to == assigned_to]

        # Resolve entity names
        summaries: list[AlertSummaryDTO] = []
        for a in alerts:
            entity = uow.entities.get(a.entity_id)
            name = entity.name if entity else a.entity_id
            summaries.append(_alert_to_summary(a, name))

    total = len(summaries)
    start = (pagination.page - 1) * pagination.limit
    page_items = summaries[start: start + pagination.limit]
    return success_response(paginate(page_items, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/{alert_id}", response_model=APIResponse[AlertDetailDTO])
async def get_alert(alert_id: str, request: Request):
    with UnitOfWork() as uow:
        alert = uow.alerts.get(alert_id)
        if alert is None:
            return _not_found(request, alert_id)
        entity = uow.entities.get(alert.entity_id)
        name = entity.name if entity else alert.entity_id
        return success_response(_alert_to_detail(alert, name))


@router.patch("/{alert_id}/action", response_model=APIResponse[AlertDetailDTO])
async def act_on_alert(alert_id: str, body: AlertActionRequest, request: Request):
    with UnitOfWork() as uow:
        alert = uow.alerts.get(alert_id)
        if alert is None:
            return _not_found(request, alert_id)
        alert.status = _ACTION_TO_STATUS[body.action]
        uow.commit()
        entity = uow.entities.get(alert.entity_id)
        name = entity.name if entity else alert.entity_id
        return success_response(
            _alert_to_detail(alert, name),
            message=f"Alert {body.action.lower()}d.",
        )
