"""Drill router — red-team detection-health metric (design doc Loop D, sequence 6.4).

Backs the dashboard's DetectionHealth card. `GET /drill/latest` returns the most
recent drill report (screening robustness vs deterministic name-evasion variants);
`POST /drill/run` forces a fresh drill.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import APIResponse, success_response
from app.services.red_team_drill import get_latest_report, run_drill

router = APIRouter(prefix="/drill", tags=["drill"])


@router.get("/latest", response_model=APIResponse[dict])
async def latest_drill() -> APIResponse[dict]:
    return success_response(get_latest_report().as_dict())


@router.post("/run", response_model=APIResponse[dict])
async def run_drill_now() -> APIResponse[dict]:
    return success_response(run_drill().as_dict(), message="Drill executed.")
