"""FastAPI application entrypoint: app factory, middleware, and router registration."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import alerts, audit, entities, health, sar, sse, watchlist
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # No DB/broker/cache to start up yet in Sprint 1 (API shell, hardcoded data).
    yield


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