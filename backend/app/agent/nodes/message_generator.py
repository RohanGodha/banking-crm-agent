"""MessageGenerator node — parallel WhatsApp drafts via Groq (volume), grounded."""
from __future__ import annotations

import asyncio

from app.agent.state import AgentState, DraftRecord, TraceEvent
from app.application.tool_registry import invoke_tool
from app.domain import ScoreBreakdown


async def _draft_for(state: AgentState, candidate) -> DraftRecord | None:
    feats = [ScoreBreakdown(**f) for f in candidate.top_features[:3] if isinstance(f, dict)]
    envelope = await invoke_tool(
        "generate_whatsapp_message",
        {
            "customer_id": candidate.customer_id,
            "product_id": candidate.recommended_product_id,
            "tone": (state.plan.tone if state.plan else "professional"),
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
    tasks = [_draft_for(state, c) for c in state.candidates]
    results = await asyncio.gather(*tasks)
    state.drafts = [r for r in results if r is not None]
    return state
