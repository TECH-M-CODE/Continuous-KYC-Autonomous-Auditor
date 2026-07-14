"""Health check endpoint. No auth required (see docs/api_contract.md)."""
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas import APIResponse, success_response

router = APIRouter(tags=["health"])

_PROCESS_START = time.monotonic()


class HealthData(BaseModel):
    status: str
    service: str
    version: str
    uptime_seconds: float
    components: dict[str, str]


@router.get("/health", response_model=APIResponse[HealthData])
async def get_health() -> APIResponse[HealthData]:
    data = HealthData(
        status="ok",
        service="CXKYC - Continuous KYC Autonomous Auditor",
        version="0.1.0",
        uptime_seconds=round(time.monotonic() - _PROCESS_START, 3),
        # Sprint 1 = API shell only; these subsystems belong to other devs and aren't wired yet.
        components={
            "database": "not_wired",
            "vector_store": "not_wired",
            "cache": "not_wired",
            "broker": "not_wired",
        },
    )
    return success_response(data, message="Service is healthy")
