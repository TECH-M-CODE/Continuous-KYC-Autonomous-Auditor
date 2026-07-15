"""Supervisor — LangGraph StateGraph wiring all agent nodes.

The graph is compiled once at module import time using ``MemorySaver``
as the in-process checkpointer. The public interface is ``run_pipeline()``,
which Loop B calls for every unprocessed RawEvent.

Node routing (conditional edges)
---------------------------------

    monitor ──► route_after_monitor ──► "screened_out" → END
                                    └──► resolver

    resolver ──► route_after_resolver ──► "dismissed"     → END
                                      ├──► "review_queued" → END
                                      └──► investigator

    investigator ──► reporter ──► END

Error path: if any node sets ``state["error"]``, the graph routes to END
immediately rather than crashing. The RawEvent stays unprocessed so Loop B
retries it next cycle.

LLM Gateway is constructed once per process and injected into the nodes that
need it via ``functools.partial``. This keeps nodes unit-testable by
accepting ``gateway`` as a kwarg.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from typing import Any

from langgraph.graph import StateGraph, END

from app.agents.state import AuditorState
from app.agents.monitor import monitor
from app.agents.resolver import resolver
from app.agents.investigator import investigator
from app.agents.reporter import reporter
from app.infrastructure.gemini_client import build_client
from app.infrastructure.llm_gateway import LLMGateway
from app.models.events import RawEvent

log = logging.getLogger(__name__)


# ── Gateway singleton (built once, reused for every pipeline call) ───────────

_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    """Return the module-level LLMGateway, building it on first call."""
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway(client=build_client())
        log.info("LLMGateway initialised (client=%s)", type(_gateway._client).__name__)
    return _gateway


# ── Routing functions ────────────────────────────────────────────────────────

def _route_after_monitor(state: AuditorState) -> str:
    if state.get("error"):
        return END
    final = state.get("final_outcome", "")
    if final == "screened_out":
        return END
    return "resolver"


def _route_after_resolver(state: AuditorState) -> str:
    if state.get("error"):
        return END
    final = state.get("final_outcome", "")
    if final in ("dismissed", "review_queued"):
        return END
    return "investigator"


# ── Graph construction ────────────────────────────────────────────────────────

def _build_graph(gw: LLMGateway) -> Any:
    """Build and compile the LangGraph StateGraph with injected gateway."""
    # Partially apply gateway so nodes remain callable(state) -> state
    _resolver = functools.partial(resolver, gateway=gw)
    _investigator = functools.partial(investigator, gateway=gw)
    _reporter = functools.partial(reporter, gateway=gw)

    graph = StateGraph(AuditorState)

    graph.add_node("monitor", monitor)
    graph.add_node("resolver", _resolver)
    graph.add_node("investigator", _investigator)
    graph.add_node("reporter", _reporter)

    graph.set_entry_point("monitor")

    graph.add_conditional_edges("monitor", _route_after_monitor, {
        "resolver": "resolver",
        END: END,
    })

    graph.add_conditional_edges("resolver", _route_after_resolver, {
        "investigator": "investigator",
        END: END,
    })

    graph.add_edge("investigator", "reporter")
    graph.add_edge("reporter", END)

    return graph.compile()


_compiled_graph: Any = None


def _get_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph(get_gateway())
    return _compiled_graph


# ── Public entry point ────────────────────────────────────────────────────────

async def run_pipeline(event: RawEvent) -> AuditorState:
    """Process one RawEvent through the full agent graph.

    This is the ``handler`` Loop B passes to ``poll_unprocessed_events``.
    It is async so it can live in the FastAPI event loop alongside the
    ingestion scheduler without blocking.

    LangGraph's synchronous ``graph.invoke()`` is run in a thread via
    ``asyncio.to_thread`` so it does not block the event loop.
    """
    log.info("run_pipeline: event_id=%s", event.id)

    # Parse content blob
    try:
        event_raw = json.loads(event.content or "{}")
    except (json.JSONDecodeError, TypeError):
        event_raw = {"text": event.content or "", "source": "unknown"}

    initial_state: AuditorState = {
        "event_id": event.id,
        "event_raw": event_raw,
        "entity_id": None,
        "entity_name": None,
        "entity_risk_score": 0.0,
        "entity_jurisdiction": None,
        "entity_persons": [],
        "match_score": 0.0,
        "screening_matches": [],
        "llm_verdict_confidence": None,
        "llm_degraded": False,
        "confidence": 0.0,
        "band": "dismiss",
        "event_type": None,
        "severity": 0.0,
        "jurisdiction_factor": 1.0,
        "score_delta": 0.0,
        "new_risk_score": 0.0,
        "risk_band": "LOW",
        "risk_event_id": None,
        "evidence": [],
        "investigation_summary": None,
        "alert_id": None,
        "sar_id": None,
        "trace": None,  # TraceBuilder created inside monitor
        "final_outcome": "",
        "error": None,
    }

    graph = _get_graph()

    try:
        final_state: AuditorState = await asyncio.to_thread(
            graph.invoke, initial_state, {"recursion_limit": 20}
        )
    except Exception as exc:  # noqa: BLE001
        log.error("run_pipeline: graph execution failed for event=%s: %s", event.id, exc)
        return {**initial_state, "error": str(exc), "final_outcome": ""}  # type: ignore[return-value]

    # Mark the event processed for every terminal outcome that isn't an error.
    # The reporter node already flags critical/SAR-path events, but screened_out,
    # dismissed, review_queued, and medium/high-alert paths route to END before
    # the reporter -- without this they would be re-drawn by Loop B every cycle,
    # flooding duplicate alerts and audit rows. An event left in an error state is
    # deliberately NOT marked, so Loop B retries it next cycle.
    if not final_state.get("error"):
        _mark_processed(event.id)

    log.info(
        "run_pipeline: DONE event=%s outcome=%s alert=%s",
        event.id,
        final_state.get("final_outcome"),
        final_state.get("alert_id"),
    )
    return final_state


def _mark_processed(event_id: str) -> None:
    """Flag a RawEvent as processed so Loop B does not re-draw it. Idempotent."""
    from app.repositories.unit_of_work import UnitOfWork

    with UnitOfWork() as uow:
        raw = uow.events.get(event_id)
        if raw is not None and not raw.processed:
            raw.processed = True
            raw.status = "PROCESSED"
            uow.commit()


__all__ = ["run_pipeline", "get_gateway"]
