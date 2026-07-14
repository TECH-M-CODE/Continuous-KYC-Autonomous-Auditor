"""Real Gemini client — implements LLMClient protocol for the LLM Gateway.

Sprint 3: swap MockLLMClient for this when GOOGLE_API_KEY is set.
The gateway's degradation ladder (retry → fallback → cache → degrade) is
unchanged; only the client underneath the gateway is replaced.

Design constraints:
* Same single async method as MockLLMClient: ``generate(prompt, model, task_tag) -> str``
* Returns a raw JSON string (the gateway owns parsing and schema validation).
* Forces JSON-only output via a system instruction — the gateway will treat any
  non-JSON response as a call failure and advance the ladder.
* Never raises for provider failures; let them propagate up — the gateway's
  try/except in ``_try_once`` handles them. CancelledError is always re-raised.
* Activated only when ``GOOGLE_API_KEY`` (or ``GEMINI_API_KEY``) is in the env.
  ``build_client()`` returns a MockLLMClient if no key is found, so the demo
  always runs even without a real API key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# The gateway will call generate() with these model strings from llm_mock.py.
# Map them to real Gemini model IDs.
_MODEL_MAP: dict[str, str] = {
    "gemini-3.1-flash-lite": "gemini-1.5-flash-8b",   # lightweight, fast
    "gemini-flash": "gemini-1.5-flash",                # fallback
}

_SYSTEM_INSTRUCTION = (
    "You are a compliance AI. You MUST respond with ONLY valid JSON matching "
    "the schema requested. Do not include markdown fences, explanations, or "
    "any text outside the JSON object."
)


class GeminiClient:
    """Real Gemini client implementing the LLMClient protocol.

    Uses ``google.generativeai`` synchronous API wrapped in
    ``asyncio.to_thread`` so it fits the async gateway without blocking the
    event loop (Gemini SDK does not yet have a native async client).
    """

    __slots__ = ("_api_key",)

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Lazy import — only required in Sprint 3 when this client is actually used.
        try:
            import google.generativeai as genai  # noqa: F401 (verify importable)
            genai.configure(api_key=api_key)
            log.info("GeminiClient initialised — real Gemini calls are ACTIVE")
        except ImportError as exc:
            raise ImportError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai>=0.8"
            ) from exc

    async def generate(self, prompt: str, *, model: str, task_tag: str) -> str:
        """Call Gemini and return a raw JSON string.

        asyncio.to_thread keeps the event loop free while the synchronous
        SDK call is in-flight.  Any exception (transport, quota, etc.) is
        allowed to propagate — the gateway's ``_try_once`` catches it.
        """
        mapped_model = _MODEL_MAP.get(model, "gemini-1.5-flash")
        log.debug("GeminiClient.generate: model=%s task_tag=%s", mapped_model, task_tag)

        def _sync_call() -> str:
            import google.generativeai as genai

            client = genai.GenerativeModel(
                model_name=mapped_model,
                system_instruction=_SYSTEM_INSTRUCTION,
                generation_config={"response_mime_type": "application/json"},
            )
            response = client.generate_content(prompt)
            return response.text

        raw = await asyncio.to_thread(_sync_call)

        # Validate it's parseable JSON before returning — the gateway does its
        # own schema validation, but a quick parse here catches obvious failures
        # early and produces a cleaner error trace.
        try:
            json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(f"Gemini returned non-JSON for {task_tag!r}: {exc}") from exc

        return raw


def build_client() -> Any:
    """Return a real GeminiClient if an API key is available, else MockLLMClient.

    Checks both ``GOOGLE_API_KEY`` and ``GEMINI_API_KEY`` for convenience.
    This is the single factory the gateway uses at startup — callers never
    need to branch on whether Gemini is live.
    """
    from app.infrastructure.llm_mock import MockLLMClient

    key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not key:
        log.warning(
            "No GOOGLE_API_KEY / GEMINI_API_KEY found — LLM calls will use MockLLMClient"
        )
        return MockLLMClient()

    try:
        return GeminiClient(api_key=key)
    except ImportError:
        log.warning(
            "google-generativeai not importable — falling back to MockLLMClient. "
            "Install with: pip install google-generativeai>=0.8"
        )
        return MockLLMClient()


__all__ = ["GeminiClient", "build_client"]
