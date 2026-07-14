"""Shared FastAPI dependencies for the API layer."""
from dataclasses import dataclass

from fastapi import Query

# No auth module exists yet (see docs/api_contract.md's Auth Module). Every route that
# will eventually require an authenticated user depends on this placeholder instead of
# a real JWT check, so swapping in real auth later only touches this one function.
SYSTEM_USER_ID = "system"


@dataclass
class PaginationParams:
    page: int
    limit: int


def pagination_params(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


async def get_current_user_id() -> str:
    return SYSTEM_USER_ID
