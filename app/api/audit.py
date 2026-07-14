"""Audit router: Sprint 1 returns hardcoded data matching docs/api_contract.md #5."""
import hashlib

from fastapi import APIRouter, Depends

from app.api.deps import PaginationParams, pagination_params
from app.schemas import APIResponse, PaginatedData, paginate, success_response
from app.schemas.audit import AuditEntryDTO, AuditVerifyDTO

router = APIRouter(prefix="/audit", tags=["audit"])

GENESIS_HASH = "GENESIS"
SYSTEM_USER_ID = "system"


def _entry_hash(previous_hash: str, action: str, payload: dict, timestamp: str) -> str:
    content = f"{previous_hash}|{action}|{payload}|{timestamp}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _build_chain(entity_id: str, steps: list[tuple[str, dict, str]]) -> list[AuditEntryDTO]:
    entries: list[AuditEntryDTO] = []
    previous_hash = GENESIS_HASH
    for index, (action, payload, timestamp) in enumerate(steps):
        entry_hash = _entry_hash(previous_hash, action, payload, timestamp)
        entries.append(
            AuditEntryDTO(
                id=f"audit-{entity_id}-{index + 1}",
                entity_id=entity_id,
                actor_id=SYSTEM_USER_ID,
                action=action,
                payload=payload,
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                signature=None,
                timestamp=timestamp,
            )
        )
        previous_hash = entry_hash
    return entries


_MOCK_AUDIT_LOG: dict[str, list[AuditEntryDTO]] = {
    "entity-1": _build_chain(
        "entity-1",
        [
            ("ENTITY_CREATED", {"name": "Acme Import Export Ltd"}, "2026-07-01T09:00:00Z"),
            ("SCORE_UPDATED", {"score_delta": 25.0, "score_after": 78.5}, "2026-07-12T14:05:00Z"),
            ("ALERT_CREATED", {"alert_id": "alert-1", "priority": "CRITICAL"}, "2026-07-12T14:05:05Z"),
        ],
    ),
}


@router.get("/verify", response_model=APIResponse[AuditVerifyDTO])
async def verify_audit_chain() -> APIResponse[AuditVerifyDTO]:
    return success_response(AuditVerifyDTO(is_valid=True, broken_at_hash=None))


@router.get("/{entity_id}", response_model=APIResponse[PaginatedData[AuditEntryDTO]])
async def get_audit_trail(
    entity_id: str,
    pagination: PaginationParams = Depends(pagination_params),
) -> APIResponse[PaginatedData[AuditEntryDTO]]:
    entries = _MOCK_AUDIT_LOG.get(entity_id, [])

    total = len(entries)
    start = (pagination.page - 1) * pagination.limit
    page_items = entries[start : start + pagination.limit]

    return success_response(paginate(page_items, total=total, page=pagination.page, page_size=pagination.limit))
