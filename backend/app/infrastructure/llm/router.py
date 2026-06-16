"""LLMRouter — cognitive-load-based routing across Gemini, Groq, and Mock.

Routing rules
─────────────
  reasoning  (planner, critic, synthesizer)  → Gemini  → Groq  → Mock
  generation (whatsapp drafts, parallel)     → Groq    → Gemini → Mock
  embed      (RAG)                           → Gemini → Mock

If a provider raises or returns no usable output, we fall through to the next.
Tracks `route_used` per call so the trace surfaces which model answered.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from app.observability import get_logger
from app.settings import get_settings

from .base import LLMClient, LLMMessage, LLMResponse
from .mock import MockLLM

logger = get_logger(__name__)

RoleKind = Literal["reasoning", "generation", "embed"]


class LLMRouter:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._gemini: LLMClient | None = None
        self._groq: LLMClient | None = None
        self._mock: LLMClient = MockLLM()

    # ---- lazy provider construction ----
    def _gem(self) -> LLMClient | None:
        if self._gemini is not None:
            return self._gemini
        if not self.settings.gemini_api_key:
            return None
        try:
            from .gemini import GeminiClient

            self._gemini = GeminiClient()
            return self._gemini
        except Exception as e:  # noqa: BLE001
            logger.warning("Gemini unavailable: %s", e)
            return None

    def _grq(self) -> LLMClient | None:
        if self._groq is not None:
            return self._groq
        if not self.settings.groq_api_key:
            return None
        try:
            from .groq import GroqClient

            self._groq = GroqClient()
            return self._groq
        except Exception as e:  # noqa: BLE001
            logger.warning("Groq unavailable: %s", e)
            return None

    def _order(self, kind: RoleKind) -> list[LLMClient]:
        gem = self._gem()
        grq = self._grq()
        if kind == "reasoning":
            order = [c for c in (gem, grq) if c]
        elif kind == "generation":
            order = [c for c in (grq, gem) if c]
        else:  # embed
            order = [c for c in (gem,) if c]
        if not order:
            return [self._mock]
        return order + [self._mock]

    # ---- public API ----
    async def complete(
        self,
        kind: RoleKind,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        last_err: Exception | None = None
        order = self._order(kind)
        for client in order:
            # Real providers get one retry (with a short backoff) before we fall
            # through — smooths transient 429s on free tiers so we don't drop to mock.
            attempts = 1 if client.name == "mock" else 2
            for attempt in range(attempts):
                try:
                    resp = await client.complete(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )
                    resp.meta["route_used"] = client.name
                    resp.meta["route_kind"] = kind
                    return resp
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    if attempt + 1 < attempts:
                        import asyncio
                        await asyncio.sleep(0.8 * (attempt + 1))
                        logger.info("%s.complete retry %d (%s): %s", client.name, attempt + 1, e.__class__.__name__, e)
                    else:
                        logger.warning("%s.complete failed (%s): %s — falling through.", client.name, e.__class__.__name__, e)
        # Final safety: always return *something* (mock never fails)
        raise RuntimeError(f"All LLM providers failed: {last_err}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        for client in self._order("embed"):
            try:
                return await client.embed(texts)
            except Exception as e:  # noqa: BLE001
                logger.warning("%s.embed failed (%s) — falling through.", client.name, e.__class__.__name__)
        return await self._mock.embed(texts)

    def status(self) -> dict[str, bool]:
        return {
            "gemini": self._gem() is not None,
            "groq": self._grq() is not None,
            "mock": True,
        }


@lru_cache(maxsize=1)
def get_llm_router() -> LLMRouter:
    return LLMRouter()
