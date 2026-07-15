"""FastAPI application entrypoint: app factory, middleware, and router registration."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, alerts, audit, drill, entities, health, sar, sse, watchlist
from app.api.admin import inject_adapter
from app.api.pipeline import router as pipeline_router
from app.config import settings
from app.services.ingestion.base import AdapterRegistry, build_scheduler, poll_unprocessed_events
from app.services.ingestion.provided_dataset import ProvidedDatasetAdapter
from app.services.ingestion.sanctions_list import SanctionsListAdapter
from app.services.ingestion.transactions import TransactionReplayAdapter
from app.services.ingestion.news_rss import NewsRSSAdapter


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # ── 1. Ensure all DB tables exist (idempotent) ────────────────────────────
    # Must run before any adapter or route touches the DB.
    from app.models.base import Base, engine
    import app.models.entities   # noqa: F401 — register models with Base
    import app.models.events     # noqa: F401
    import app.models.risk       # noqa: F401
    import app.models.sar        # noqa: F401
    import app.models.audit      # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Adapters are constructed here (not at module import time) since
    # TransactionReplayAdapter loads + sorts the sampled parquet in
    # __init__ -- a real cost that must not happen just from importing
    # app.main (e.g. during test collection).
    registry = AdapterRegistry()
    registry.register(ProvidedDatasetAdapter())
    registry.register(SanctionsListAdapter())
    registry.register(TransactionReplayAdapter())
    registry.register(NewsRSSAdapter())          # live adverse media (Reuters/GDELT)
    registry.register(inject_adapter)            # shared with app.api.admin's route handler

    scheduler = build_scheduler(registry)

    # Loop D: autonomous self-assessment (red-team drill + dormancy sweep).
    # Registered on the same scheduler as the ingest adapters; the design runs it
    # nightly, but the interval is configurable (0 disables it).
    if settings.loop_d_interval_seconds > 0:
        from datetime import datetime, timedelta, timezone
        from app.services.loop_d import run_loop_d

        scheduler.add_job(
            run_loop_d,
            trigger="interval",
            seconds=settings.loop_d_interval_seconds,
            id="loop_d_self_assessment",
            # First run shortly after boot (not at t=0) so ingest adapters seed the
            # sanctions cache the drill screens against.
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=20),
            max_instances=1,
            coalesce=True,
        )

    scheduler.start()

    # Sprint 3: wire the real agent pipeline to Loop B
    from app.agents.supervisor import run_pipeline
    loop_b_task = asyncio.create_task(poll_unprocessed_events(handler=run_pipeline))

    yield

    loop_b_task.cancel()
    try:
        await loop_b_task
    except asyncio.CancelledError:
        pass
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.project_name,
    docs_url=f"{settings.api_v1_prefix}/docs",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def attach_trace_id(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected error occurred.",
            "data": None,
            "trace_id": trace_id,
            "error_code": "ERR_INTERNAL",
        },
    )


@app.get("/")
async def root():
    return {
        "message": "Welcome to SentinelAI Continuous KYC Auditor API"
    }


app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(entities.router, prefix=settings.api_v1_prefix)
app.include_router(alerts.router, prefix=settings.api_v1_prefix)
app.include_router(sar.router, prefix=settings.api_v1_prefix)
app.include_router(audit.router, prefix=settings.api_v1_prefix)
app.include_router(watchlist.router, prefix=settings.api_v1_prefix)
app.include_router(sse.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)
app.include_router(drill.router, prefix=settings.api_v1_prefix)
app.include_router(pipeline_router, prefix=settings.api_v1_prefix)