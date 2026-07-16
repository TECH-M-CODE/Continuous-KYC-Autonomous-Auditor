"""SAR router — Sprint 3: real DB reads replacing the Sprint 1 mock store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.sar import (
    CitationDTO,
    SARDecisionRequest,
    SARDetailDTO,
    SARSummaryDTO,
    SARUpdateRequest,
    SARVersionDTO,
)
from app.services.sar_service import get_citations
from app.services.audit_service import append_audit

router = APIRouter(prefix="/sars", tags=["sars"])

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


def _citations_to_dtos(sar) -> list[CitationDTO]:
    raw = get_citations(sar)
    dtos = []
    for c in raw:
        # Support both {citation, passage} and {source, context}
        source = c.get("citation") or c.get("source", "")
        context = c.get("passage") or c.get("context", "")
        dtos.append(CitationDTO(source=source, context=context))
    return dtos


def _sar_to_detail(sar, entity_name: str = "") -> SARDetailDTO:
    return SARDetailDTO(
        id=sar.id,
        alert_id=sar.alert_id or "",
        version=sar.version,
        status=sar.status,
        narrative=sar.narrative or "",
        citations=_citations_to_dtos(sar),
        previous_versions=[],
    )


def _sar_to_summary(sar, entity_name: str) -> SARSummaryDTO:
    return SARSummaryDTO(
        id=sar.id,
        alert_id=sar.alert_id or "",
        entity_name=entity_name,
        version=sar.version,
        status=sar.status,
        created_at=sar.created_at,
    )


@router.get("", response_model=APIResponse[PaginatedData[SARSummaryDTO]])
async def list_sars(
    pagination: PaginationParams = Depends(pagination_params),
    status: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[SARSummaryDTO]]:
    with UnitOfWork() as uow:
        sars = uow.sars.list(
            status=status.upper() if status else None
        )
        summaries: list[SARSummaryDTO] = []
        for sar in sars:
            entity = uow.entities.get(sar.entity_id)
            name = entity.name if entity else sar.entity_id
            summaries.append(_sar_to_summary(sar, name))

    total = len(summaries)
    start = (pagination.page - 1) * pagination.limit
    page_items = summaries[start: start + pagination.limit]
    return success_response(paginate(page_items, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/{sar_id}", response_model=APIResponse[SARDetailDTO])
async def get_sar(sar_id: str, request: Request):
    with UnitOfWork() as uow:
        sar = uow.sars.get(sar_id)
        if sar is None:
            return _not_found(request, sar_id)
        entity = uow.entities.get(sar.entity_id)
        name = entity.name if entity else sar.entity_id
        return success_response(_sar_to_detail(sar, name))


@router.put("/{sar_id}", response_model=APIResponse[SARDetailDTO])
async def update_sar(sar_id: str, body: SARUpdateRequest, request: Request):
    with UnitOfWork() as uow:
        sar = uow.sars.get(sar_id)
        if sar is None:
            return _not_found(request, sar_id)
        sar.version += 1
        sar.narrative = body.narrative
        sar.citations = json.dumps(
            [{"citation": c.source, "passage": c.context} for c in body.citations]
        )
        sar.status = "DRAFT"

        append_audit(
            action="SAR_EDITED",
            payload={
                "sar_id": sar.id,
                "version": sar.version,
                "detail": "SAR narrative edited via UI.",
            },
            uow=uow,
            entity_id=sar.entity_id,
            actor_id="human",
        )
        uow.commit()
        return success_response(_sar_to_detail(sar), message="SAR draft updated to a new version.")


@router.post("/{sar_id}/decision", response_model=APIResponse[SARDetailDTO])
async def decide_sar(sar_id: str, body: SARDecisionRequest, request: Request):
    with UnitOfWork() as uow:
        sar = uow.sars.get(sar_id)
        if sar is None:
            return _not_found(request, sar_id)
        sar.status = _DECISION_TO_STATUS[body.decision]

        # Close out the alert that triggered this SAR so it leaves the active
        # queue once a human has adjudicated it: approve -> RESOLVED, reject ->
        # DISMISSED.
        if sar.alert_id:
            alert = uow.alerts.get(sar.alert_id)
            if alert and alert.status.upper() in ("OPEN", "ESCALATED", "IN_PROGRESS"):
                alert.status = "RESOLVED" if body.decision == "APPROVE" else "DISMISSED"

        append_audit(
            action=f"SAR_{body.decision.upper()}",
            payload={
                "sar_id": sar.id,
                "decision": body.decision,
                "comments": body.comments,
            },
            uow=uow,
            entity_id=sar.entity_id,
            actor_id="human",
        )
        uow.commit()
        return success_response(_sar_to_detail(sar), message=f"SAR decision recorded: {body.decision}.")

from pydantic import BaseModel

class SARRequestInfoBody(BaseModel):
    question: str


class _InvestigatorAnswer(BaseModel):
    answer: str


@router.post("/{sar_id}/request-info", response_model=APIResponse[dict])
async def request_sar_info(sar_id: str, body: SARRequestInfoBody, request: Request):
    # Snapshot the SAR context + write the audit row, then release the UoW before
    # the (slower) LLM call so we don't hold a DB transaction open across the network.
    with UnitOfWork() as uow:
        sar = uow.sars.get(sar_id)
        if sar is None:
            return _not_found(request, sar_id)

        entity = uow.entities.get(sar.entity_id)
        entity_name = entity.name if entity else sar.entity_id
        narrative = sar.narrative or ""
        citations = get_citations(sar)

        append_audit(
            action="INFO_REQUESTED",
            payload={"sar_id": sar.id, "question": body.question},
            uow=uow,
            entity_id=sar.entity_id,
            actor_id="human",
        )
        uow.commit()

    # Ask the same LLM that authored the SAR to answer the reviewer's follow-up,
    # grounded in this SAR's narrative + cited evidence.
    from app.agents.supervisor import get_gateway

    prompt = (
        f"You are the compliance investigator AI that produced the Suspicious Activity Report "
        f"below for entity '{entity_name}'. A human MLRO reviewer is asking a follow-up question. "
        f"Answer concisely and specifically, grounded ONLY in the SAR narrative and cited evidence. "
        f"If the answer is not supported by the evidence, say so and state what additional check "
        f"would be required.\n\n"
        f"SAR NARRATIVE:\n{narrative}\n\n"
        f"CITED EVIDENCE:\n{json.dumps(citations)[:2000]}\n\n"
        f"REVIEWER QUESTION: {body.question}\n\n"
        f'Respond as JSON: {{"answer": "<your answer>"}}'
    )

    try:
        result = await get_gateway().complete(
            prompt, schema=_InvestigatorAnswer, task_tag="investigator_qa"
        )
    except Exception:  # noqa: BLE001 — never fail the endpoint on an LLM error
        result = None

    if result is not None and result.ok and result.data:
        answer = result.data.answer
        degraded = False
    else:
        degraded = True
        answer = (
            "The investigator agent is temporarily unavailable (LLM degraded). "
            f"From the SAR on record: {narrative[:400] or 'no narrative available.'}"
        )

    return success_response(
        {"status": "answered", "question": body.question, "answer": answer, "degraded": degraded},
        message="Investigator responded.",
    )
