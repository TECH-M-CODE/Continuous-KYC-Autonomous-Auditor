"""Admin router: the demo trigger button (docs/implementation_plan.md Sprint 2, Dev 4, Hour 3).

Mounted under the app's existing /api/v1 prefix like every other router, for
consistency with the rest of the API -- the Sprint 2 plan's literal
"/api/admin/inject" path omits versioning the same way it writes
"/api/traces/{event_id}" without a prefix elsewhere.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas import APIResponse, success_response
from app.services.ingestion.inject import InjectAdapter
from demo.scenario_engine import run_scenario

router = APIRouter(prefix="/admin", tags=["admin"])

# Single shared instance: main.py imports this same object to register into
# the AdapterRegistry, so Loop A's safety-net drain and this route's
# immediate persistence operate on one InjectAdapter, not two.
inject_adapter = InjectAdapter()


class InjectRequest(BaseModel):
    event_type: str
    title: str
    text: str
    entity_hint: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    is_drill: bool = False


class InjectResponseData(BaseModel):
    injected: bool
    event_type: str
    title: str


class DemoPlayRequest(BaseModel):
    scenario: str
    entity_id: str | None = None


@router.get("/drill/latest", response_model=APIResponse[dict])
async def get_latest_drill() -> APIResponse[dict]:
    # Stub for the drill report to prevent 404s in the frontend
    return success_response({"status": "no_active_drill"}, message="No active drill.")


@router.post("/demo/play", response_model=APIResponse[dict])
async def play_demo_scenario(body: DemoPlayRequest) -> APIResponse[dict]:
    try:
        result = await run_scenario(body.scenario, body.entity_id)
        return success_response(result, message=f"Scenario {body.scenario} completed successfully.")
    except ValueError as e:
        return APIResponse(
            success=False,
            message=str(e),
            data={},
            error_code="ERR_INVALID_SCENARIO"
        )



@router.post("/inject", response_model=APIResponse[InjectResponseData])
async def inject_event(body: InjectRequest) -> APIResponse[InjectResponseData]:
    ingested = inject_adapter.inject_now(
        event_type=body.event_type,
        title=body.title,
        text=body.text,
        entity_hint=body.entity_hint,
        payload=body.payload,
        is_drill=body.is_drill,
    )

    if ingested is None:
        return success_response(
            InjectResponseData(injected=False, event_type=body.event_type, title=body.title),
            message="Event already exists (deduped); nothing new injected.",
        )

    return success_response(
        InjectResponseData(injected=True, event_type=body.event_type, title=body.title),
        message="Event injected.",
    )
