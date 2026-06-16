"""MessageGenerator node — concurrency-limited WhatsApp drafts (grounded).

Free-tier LLMs have per-minute request limits. Firing 10 drafts at once can trip
429s and silently fall through to the offline mock. We cap concurrency with a
semaphore so the burst stays under the rate limit while remaining fast.
"""
from __future__ import annotations

import asyncio

from app.agent.state import AgentState, DraftRecord, TraceEvent
from app.application.tool_registry import invoke_tool
from app.domain import ScoreBreakdown

# Max simultaneous draft generations (keeps us under Groq/Gemini free RPM).
_MAX_CONCURRENCY = 4


async def _draft_for(state: AgentState, candidate) -> DraftRecord | None:
    feats = [ScoreBreakdown(**f) for f in candidate.top_features[:3] if isinstance(f, dict)]
    envelope = await invoke_tool(
        "generate_whatsapp_message",
        {
            "customer_id": candidate.customer_id,
            "product_id": candidate.recommended_product_id,
            "tone": (state.plan.tone if state.plan else "professional"),
            "language": (state.plan.language if state.plan else "English"),
            "top_features": [f.model_dump() for f in feats],
            "rm_name": state.rm_name,
        },
    )
    if not envelope["ok"]:
        return None
    data = envelope["data"]
    rec = DraftRecord(
        customer_id=candidate.customer_id,
        product_id=candidate.recommended_product_id,
        message=data.get("message", ""),
        compliance=data.get("compliance", {}),
        llm_route=data.get("llm_route", ""),
    )
    state.emit(TraceEvent(
        event="draft",
        data={
            "customer_id": rec.customer_id,
            "product_id": rec.product_id,
            "message": rec.message,
            "compliance": rec.compliance,
            "llm_route": data.get("llm_route"),
        },
        llm_route=data.get("llm_route"),
        latency_ms=data.get("latency_ms"),
    ))
    return rec


async def run_message_generator(state: AgentState) -> AgentState:
    if not state.candidates:
        state.emit(TraceEvent(event="info", data={"msg": "no candidates → skipping drafts"}))
        return state
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    async def _bounded(c):
        async with sem:
            return await _draft_for(state, c)

    results = await asyncio.gather(*[_bounded(c) for c in state.candidates])
    state.drafts = [r for r in results if r is not None]
    return state
