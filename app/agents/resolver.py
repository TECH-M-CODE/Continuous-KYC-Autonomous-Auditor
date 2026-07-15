"""Resolver node — LLM verdict + confidence blending.

Responsibilities
----------------
1. Call LLM Gateway: task_tag="resolver_verdict" to get a match verdict.
2. Call ``verify()`` with the LLM's ``llm_verdict_confidence`` to produce the
   blended confidence score (60% LLM + 40% deterministic when LLM available).
3. Emit a "resolve" and "verify" node in the TraceBuilder.
4. Route:
   - band == "dismiss"   → final_outcome = "dismissed"
   - band == "review"    → final_outcome = "review_queued"
   - band == "proceed"   → forward to investigator

Degraded-LLM path: if the gateway exhausts all rungs (degraded=True), the
deterministic score is capped at 0.74, forcing a "review" band. The system
can never auto-proceed without an LLM verdict.
"""

from __future__ import annotations

import asyncio
import logging
from pydantic import BaseModel

from app.agents.state import AuditorState
from app.agents.prompts.resolver_prompts import build_resolver_prompt
from app.services.verification import verify

log = logging.getLogger(__name__)


# ── LLM response schema ──────────────────────────────────────────────────────

class ResolverVerdict(BaseModel):
    match: bool
    confidence: float
    reasoning: str


# ── Node ────────────────────────────────────────────────────────────────────

def resolver(state: AuditorState, *, gateway) -> AuditorState:
    """Resolver node. ``gateway`` is injected by the supervisor."""
    entity_name = state.get("entity_name", "Unknown")
    log.info("resolver: entity=%s match_score=%.0f", entity_name, state.get("match_score", 0))

    tb = state["trace"]

    # ── LLM call (via degradation ladder) ────────────────────────────────────
    prompt = build_resolver_prompt(
        entity_name=entity_name,
        entity_jurisdiction=state.get("entity_jurisdiction"),
        screening_matches=state.get("screening_matches", []),
        event_text=state.get("event_raw", {}).get("text", ""),
        event_source=state.get("event_raw", {}).get("source", "unknown"),
    )

    # Run async gateway in sync context. This node runs inside asyncio.to_thread()'s
    # worker thread (see supervisor.run_pipeline), which has no event loop of its
    # own -- asyncio.get_event_loop() raises RuntimeError there. asyncio.run()
    # creates and tears down a fresh loop for this call instead.
    result = asyncio.run(
        gateway.complete(prompt, schema=ResolverVerdict, task_tag="resolver_verdict")
    )

    verdict: ResolverVerdict | None = result.data
    llm_verdict_confidence = verdict.confidence if (result.ok and verdict) else None
    llm_degraded = result.degraded

    tb.add(
        kind="resolve",
        label=f"LLM verdict: {'MATCH' if (verdict and verdict.match) else 'NO MATCH'}",
        detail=(
            verdict.reasoning if verdict
            else f"LLM degraded after {result.attempts} attempts"
        ),
        values={
            "llm_ok": result.ok,
            "llm_model": result.model_used,
            "llm_degraded": llm_degraded,
            "llm_confidence": llm_verdict_confidence,
            "llm_attempts": result.attempts,
            "from_cache": result.from_cache,
        },
        outcome="pass" if (result.ok and verdict and verdict.match) else "fail",
    )

    # ── Verification combiner ─────────────────────────────────────────────────
    # Load policy inside try so a missing policy.yaml doesn't crash the pipeline
    try:
        from app.services.scoring.policy import get_policy
        policy = get_policy()
    except Exception as exc:  # noqa: BLE001
        log.error("resolver: could not load policy: %s", exc)
        state["error"] = f"policy load failed: {exc}"
        return state

    verification = verify(
        event=state.get("event_raw", {}),
        match_score=state.get("match_score", 0.0),
        policy=policy,
        llm_verdict_confidence=llm_verdict_confidence,
        degraded=llm_degraded,
    )

    tb.add(
        kind="verify",
        label=verification.trace_label(),
        detail=verification.trace_detail(),
        values=verification.trace_values(),
        outcome="pass" if verification.band == "proceed" else "branch",
    )

    # ── Routing ───────────────────────────────────────────────────────────────
    band = verification.band  # "dismiss" | "review" | "proceed"

    state["llm_verdict_confidence"] = llm_verdict_confidence
    state["llm_degraded"] = llm_degraded
    state["confidence"] = verification.score
    state["band"] = band
    state["trace"] = tb

    if band == "dismiss":
        state["final_outcome"] = "dismissed"
    elif band == "review":
        state["final_outcome"] = "review_queued"
    # "proceed" → no final_outcome yet; investigator will set it

    return state
