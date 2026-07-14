"""Watchlist router.

NOTE: docs/api_contract.md defines no Watchlist module (no endpoints/DTOs). This shape is
inferred from docs/canonical_domain_model.md's WatchlistEntry entity and the
ISanctionsRepository interface in docs/engineering_contract.md, to unblock the
AdminWatchlist frontend page. Reconcile with the team if the contract is formally amended.
Sprint 1 returns hardcoded data.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import PaginationParams, pagination_params
from app.schemas import APIResponse, PaginatedData, paginate, success_response

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

ListSource = Literal["OFAC", "UN", "EU", "UK_HMT"]
WatchlistEntityType = Literal["COMPANY", "PERSON", "VESSEL"]


class WatchlistEntrySummaryDTO(BaseModel):
    id: str
    external_id: str
    list_source: ListSource
    entity_type: WatchlistEntityType
    primary_name: str
    is_active: bool


class WatchlistEntryDetailDTO(WatchlistEntrySummaryDTO):
    aliases: list[str]
    metadata: dict
    version: int


class WatchlistVersionDTO(BaseModel):
    list_source: ListSource
    version: int
    entry_count: int
    last_synced_at: str


_MOCK_WATCHLIST: dict[str, WatchlistEntryDetailDTO] = {
    "wl-1": WatchlistEntryDetailDTO(
        id="wl-1",
        external_id="OFAC-12345",
        list_source="OFAC",
        entity_type="PERSON",
        primary_name="Petrov, Viktor",
        is_active=True,
        aliases=["V. Petrov", "Viktor Petrovich"],
        metadata={"nationality": "Russia", "date_of_birth": "1975-03-14"},
        version=142,
    ),
    "wl-2": WatchlistEntryDetailDTO(
        id="wl-2",
        external_id="EU-98765",
        list_source="EU",
        entity_type="COMPANY",
        primary_name="Northwind Holdings SA",
        is_active=True,
        aliases=["Northwind Holdings"],
        metadata={"jurisdiction": "Luxembourg"},
        version=87,
    ),
    "wl-3": WatchlistEntryDetailDTO(
        id="wl-3",
        external_id="OFAC-00042",
        list_source="OFAC",
        entity_type="COMPANY",
        primary_name="Globex Trading",
        is_active=False,
        aliases=[],
        metadata={"delisted_at": "2019-06-01"},
        version=142,
    ),
}

_MOCK_VERSIONS: list[WatchlistVersionDTO] = [
    WatchlistVersionDTO(list_source="OFAC", version=142, entry_count=17482, last_synced_at="2026-07-14T06:00:00Z"),
    WatchlistVersionDTO(list_source="EU", version=87, entry_count=4213, last_synced_at="2026-07-14T06:00:00Z"),
    WatchlistVersionDTO(list_source="UN", version=53, entry_count=1890, last_synced_at="2026-07-13T06:00:00Z"),
    WatchlistVersionDTO(list_source="UK_HMT", version=29, entry_count=2107, last_synced_at="2026-07-13T06:00:00Z"),
]


def _not_found(request: Request, entry_id: str) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "message": f"Watchlist entry '{entry_id}' not found.",
            "data": None,
            "trace_id": trace_id,
            "error_code": "ERR_WATCHLIST_ENTRY_NOT_FOUND",
        },
    )


@router.get("", response_model=APIResponse[PaginatedData[WatchlistEntrySummaryDTO]])
async def list_watchlist_entries(
    pagination: PaginationParams = Depends(pagination_params),
    list_source: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> APIResponse[PaginatedData[WatchlistEntrySummaryDTO]]:
    entries = list(_MOCK_WATCHLIST.values())

    if list_source:
        entries = [e for e in entries if e.list_source == list_source.upper()]
    if entity_type:
        entries = [e for e in entries if e.entity_type == entity_type.upper()]
    if search:
        entries = [e for e in entries if search.lower() in e.primary_name.lower()]

    total = len(entries)
    start = (pagination.page - 1) * pagination.limit
    page_items = entries[start : start + pagination.limit]

    summaries = [
        WatchlistEntrySummaryDTO(
            id=e.id,
            external_id=e.external_id,
            list_source=e.list_source,
            entity_type=e.entity_type,
            primary_name=e.primary_name,
            is_active=e.is_active,
        )
        for e in page_items
    ]
    return success_response(paginate(summaries, total=total, page=pagination.page, page_size=pagination.limit))


@router.get("/version", response_model=APIResponse[list[WatchlistVersionDTO]])
async def get_watchlist_versions(list_source: Optional[str] = Query(None)) -> APIResponse[list[WatchlistVersionDTO]]:
    versions = _MOCK_VERSIONS
    if list_source:
        versions = [v for v in versions if v.list_source == list_source.upper()]
    return success_response(versions)


@router.get("/{entry_id}", response_model=APIResponse[WatchlistEntryDetailDTO])
async def get_watchlist_entry(entry_id: str, request: Request):
    entry = _MOCK_WATCHLIST.get(entry_id)
    if entry is None:
        return _not_found(request, entry_id)
    return success_response(entry)
