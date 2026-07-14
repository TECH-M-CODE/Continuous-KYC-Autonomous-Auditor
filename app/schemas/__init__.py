"""Shared API response envelope (see docs/api_contract.md, docs/engineering_contract.md #6)."""
import math
import uuid
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    trace_id: Optional[str] = None
    error_code: Optional[str] = None


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


def success_response(data: T, message: str = "Success", trace_id: Optional[str] = None) -> APIResponse[T]:
    return APIResponse[T](success=True, message=message, data=data, trace_id=trace_id or str(uuid.uuid4()))


def paginate(items: list[T], total: int, page: int, page_size: int) -> PaginatedData[T]:
    total_pages = math.ceil(total / page_size) if page_size else 0
    return PaginatedData[T](items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)
