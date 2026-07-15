"""NVIDIA NIM client — implements LLMClient protocol for the LLM Gateway.

NVIDIA's inference platform (NIM) is OpenAI-compatible, so we use the
``openai`` SDK with a different ``base_url``. The same degradation ladder
in LLMGateway applies unchanged — only the underlying client changes.

Priority in build_client():
  1. NVIDIA_API_KEY → NvidiaClient  (this file)
  2. GOOGLE_API_KEY / GEMINI_API_KEY → GeminiClient  (gemini_client.py)
  3. neither → MockLLMClient  (fully deterministic, no billing)

Supported models (via NVIDIA_PRIMARY_MODEL / NVIDIA_FALLBACK_MODEL env):
  • meta/llama-3.3-70b-instruct   ← default primary  (strong, fast)
  • meta/llama-3.1-8b-instruct    ← default fallback  (lightweight)
  • mistralai/mistral-large-2-instruct
  • nvidia/llama-3.1-nemotron-70b-instruct
  … any model listed at https://build.nvidia.com/explore/reasoning

Install: pip install "openai>=1.30"
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# Default NVIDIA NIM model IDs — override via env if needed
DEFAULT_NVIDIA_PRIMARY  = "meta/llama-3.3-70b-instruct"
DEFAULT_NVIDIA_FALLBACK = "meta/llama-3.1-8b-instruct"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

_SYSTEM_PROMPT = (
    "You are a compliance AI assistant. "
    "You MUST respond with ONLY valid JSON matching the schema requested. "
    "Do not include markdown fences, explanations, or any text outside the JSON object."
)


class NvidiaClient:
    """NVIDIA NIM client implementing the LLMClient protocol.

    The openai SDK is async-native so no asyncio.to_thread needed.
    The client instance is reused across all calls (built once in
    build_client, injected into LLMGateway singleton).
    """

    __slots__ = ("_client", "_api_key")

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        # Delay openai client creation to generate() so it binds to the correct event loop
        # when running in LangGraph worker threads.
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. "
                "Run: pip install 'openai>=1.30'"
            ) from exc


    async def generate(self, prompt: str, *, model: str, task_tag: str) -> str:
        """Call NVIDIA NIM and return a raw JSON string.

        ``model`` arrives as the gateway's internal alias (e.g. 'gemini-3.1-flash-lite').
        We remap it to a real NIM model ID so the gateway ladder is unchanged.
        """
        nim_model = _resolve_model(model)
        log.debug("NvidiaClient.generate: nim_model=%s task_tag=%s", nim_model, task_tag)

        import asyncio
        from openai import OpenAI
        client = OpenAI(
            api_key=self._api_key,
            base_url=NVIDIA_BASE_URL,
        )

        # Run the synchronous client call in a thread to avoid blocking the event loop
        def _call_api():
            return client.chat.completions.create(
                model=nim_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

        response = await asyncio.to_thread(_call_api)



        raw: str = response.choices[0].message.content or ""

        # Quick parse — gateway does full schema validation, but a non-JSON
        # response here means something went badly wrong at NIM level.
        try:
            json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                f"NVIDIA NIM returned non-JSON for {task_tag!r}: {exc!r} | raw={raw[:200]!r}"
            ) from exc

        return raw


# ── Model alias resolution ─────────────────────────────────────────────────────

def _resolve_model(gateway_alias: str) -> str:
    """Map the gateway's internal alias → real NIM model ID.

    Override via env:
      NVIDIA_PRIMARY_MODEL  — maps rung-1 alias
      NVIDIA_FALLBACK_MODEL — maps rung-2 alias
    """
    primary  = os.getenv("NVIDIA_PRIMARY_MODEL",  DEFAULT_NVIDIA_PRIMARY)
    fallback = os.getenv("NVIDIA_FALLBACK_MODEL", DEFAULT_NVIDIA_FALLBACK)

    _alias_map: dict[str, str] = {
        "gemini-3.1-flash-lite": primary,   # gateway rung 1
        "gemini-flash":          fallback,  # gateway rung 2
    }
    return _alias_map.get(gateway_alias, primary)


# ── Factory (NVIDIA → Gemini → Mock) ──────────────────────────────────────────

def build_client() -> Any:
    """Return the best available LLM client.

    Priority: NVIDIA → Gemini → Mock
    This is the single factory the supervisor uses at startup.
    """
    from app.config import settings
    from app.infrastructure.llm_mock import MockLLMClient

    # 1. NVIDIA NIM (preferred)
    nvidia_key = settings.nvidia_api_key or os.getenv("NVIDIA_API_KEY")
    if nvidia_key:
        try:
            client = NvidiaClient(api_key=nvidia_key)
            log.info("build_client: using NvidiaClient")
            return client
        except ImportError:
            log.warning(
                "openai package missing — cannot use NvidiaClient. "
                "Run: pip install 'openai>=1.30'. Trying Gemini next."
            )

    gemini_key = settings.google_api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from app.infrastructure.gemini_client import GeminiClient
            client = GeminiClient(api_key=gemini_key)
            log.info("build_client: using GeminiClient")
            return client
        except ImportError:
            log.warning(
                "google-generativeai missing — cannot use GeminiClient. "
                "Falling back to Mock."
            )

    # 3. Mock — no billing, fully deterministic
    log.warning(
        "No NVIDIA_API_KEY or GOOGLE_API_KEY found — "
        "LLM calls will use MockLLMClient (demo/test mode)"
    )
    return MockLLMClient()


__all__ = [
    "NvidiaClient",
    "build_client",
    "DEFAULT_NVIDIA_PRIMARY",
    "DEFAULT_NVIDIA_FALLBACK",
    "NVIDIA_BASE_URL",
]
