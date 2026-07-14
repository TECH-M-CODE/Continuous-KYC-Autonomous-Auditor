"""Audit router — Sprint 3: real DB reads + real hash-chain verification."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import PaginationParams, pagination_params
from app.repositories.unit_of_work import UnitOfWork
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.audit import AuditEntryDTO, AuditVerifyDTO
from app.services.audit_service import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])


def _entry_to_dto(entry) -> AuditEntryDTO:
    import json as _json
    try:
        payload_dict = _json.loads(entry.payload or "{}")
    except (_json.JSONDecodeError, TypeError):
        payload_dict = {}

    return AuditEntryDTO(
        id=entry.id,
        entity_id=entry.entity_id,
        actor_id=entry.actor_id,
        action=entry.action,
        payload=payload_dict,
        previous_hash=entry.prev_hash,
        entry_hash=entry.entry_hash,
        signature=entry.signature,
        timestamp=entry.timestamp,
    )


@router.get("/verify", response_model=APIResponse[AuditVerifyDTO])
async def verify_audit_chain() -> APIResponse[AuditVerifyDTO]:
    """Walk the full audit chain and verify every hash link."""
    with UnitOfWork() as uow:
        is_valid, broken_at = verify_chain(entity_id=None, uow=uow)
    return success_response(AuditVerifyDTO(is_valid=is_valid, broken_at_hash=broken_at))


@router.get("/{entity_id}", response_model=APIResponse[PaginatedData[AuditEntryDTO]])
async def get_audit_trail(
    entity_id: str,
    pagination: PaginationParams = Depends(pagination_params),
) -> APIResponse[PaginatedData[AuditEntryDTO]]:
    with UnitOfWork() as uow:
        entries = uow.audit_log.list(entity_id=entity_id)
    dtos = [_entry_to_dto(e) for e in entries]

    total = len(dtos)
    start = (pagination.page - 1) * pagination.limit
    page_items = dtos[start: start + pagination.limit]
    return success_response(paginate(page_items, total=total, page=pagination.page, page_size=pagination.limit))
