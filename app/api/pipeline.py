"""Pipeline router — HTTP trigger endpoints for the agent pipeline.

Two endpoints:
- POST /pipeline/run          trigger pipeline on a specific unprocessed event
- POST /pipeline/demo         run a named demo scenario end-to-end
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from app.schemas import APIResponse, success_response

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class RunEventRequest(BaseModel):
    event_id: str


class DemoRequest(BaseModel):
    scenario: str = "sanctions_hit"
    entity_id: str | None = None


@router.post("/run", response_model=APIResponse[dict])
async def run_event(body: RunEventRequest, background_tasks: BackgroundTasks):
    """Trigger the agent pipeline on a specific unprocessed RawEvent."""
    from app.repositories.unit_of_work import UnitOfWork
    from app.agents.supervisor import run_pipeline

    with UnitOfWork() as uow:
        event = uow.events.get(body.event_id)
        if event is None:
            raise HTTPException(status_code=404, detail=f"Event '{body.event_id}' not found")
        if event.processed:
            raise HTTPException(
                status_code=409, detail=f"Event '{body.event_id}' is already processed"
            )

    async def _run():
        from app.repositories.unit_of_work import UnitOfWork
        with UnitOfWork() as uow2:
            ev = uow2.events.get(body.event_id)
        if ev:
            await run_pipeline(ev)

    background_tasks.add_task(_run)
    return success_response(
        {"event_id": body.event_id, "status": "pipeline_started"},
        message="Pipeline started in background.",
    )


@router.post("/demo", response_model=APIResponse[dict])
async def run_demo(body: DemoRequest):
    """Run a named demo scenario end-to-end synchronously (demo/hackathon use)."""
    from demo.scenario_engine import run_scenario, ScenarioName

    valid_scenarios = ["sanctions_hit", "adverse_media_spike", "transaction_velocity"]
    if body.scenario not in valid_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario '{body.scenario}'. Valid: {valid_scenarios}",
        )

    result = await run_scenario(body.scenario, entity_id=body.entity_id)  # type: ignore[arg-type]
    return success_response(result, message=f"Scenario '{body.scenario}' completed.")
