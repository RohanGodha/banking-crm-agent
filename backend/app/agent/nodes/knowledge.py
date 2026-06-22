"""Knowledge node — answers banking/persona questions from the reference knowledge base.

If the question is answerable from the markdown knowledge base (RBI policies, customer
financial history, RM-Client FAQs) or a named customer's records, the answer is grounded
in them. Otherwise it falls back to a full LLM call for a general banking answer.
"""
from __future__ import annotations

from app.agent.prompts import SYSTEM_PROMPT
from app.agent.state import AgentState, TraceEvent
from app.infrastructure.llm import LLMMessage, get_llm_router
from app.knowledge_base import get_knowledge_base
from app.observability import get_logger

logger = get_logger(__name__)


async def run_knowledge(state: AgentState) -> AgentState:
    kb = get_knowledge_base()
    result = await kb.ask(state.rm_query)
    sources = result.get("sources") or []
    route = result.get("llm_route")

    if sources:
        state.final_summary = result["answer"]
    else:
        # Not in the knowledge base — do a full LLM call for a general banking answer.
        router = get_llm_router()
        try:
            resp = await router.complete(
                kind="reasoning",
                messages=[
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=state.rm_query),
                ],
                temperature=0.3,
                max_tokens=320,
            )
            text = resp.text.strip()
            state.final_summary = text or result["answer"]
            route = resp.meta.get("route_used", resp.provider)
        except Exception as e:  # noqa: BLE001
            logger.warning("Knowledge fallback LLM failed (%s).", e.__class__.__name__)
            state.final_summary = result["answer"]

    state.emit(TraceEvent(
        event="synth",
        data={
            "summary": state.final_summary,
            "candidate_count": 0,
            "mode": "knowledge",
            "kb_sources": sources,
        },
        llm_route=route,
    ))
    return state
