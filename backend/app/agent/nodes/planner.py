"""Planner node — turns the RM's natural-language ask into a typed Plan."""
from __future__ import annotations

from typing import Any

from app.agent.prompts import FOLLOW_UP_PROMPT, planner_prompt
from app.agent.state import AgentState, Plan, PlanStep, TraceEvent
from app.infrastructure.llm import LLMMessage, get_llm_router
from app.observability import get_logger

logger = get_logger(__name__)


def _load_system() -> str:
    return planner_prompt()


async def _rewrite_follow_up(state: AgentState) -> str:
    """Expand a refinement into a standalone task using conversation history."""
    router = get_llm_router()
    prev_user = next((h["content"] for h in reversed(state.history) if h["role"] == "user"), "")
    prev_assistant = next((h["content"] for h in reversed(state.history) if h["role"] == "assistant"), "")
    try:
        resp = await router.complete(
            kind="reasoning",
            messages=[
                LLMMessage(role="system", content=FOLLOW_UP_PROMPT),
                LLMMessage(role="user", content=(
                    f"Previous: '{prev_user}'\n"
                    f"(assistant replied: {prev_assistant[:160]})\n"
                    f"New: '{state.rm_query}'"
                )),
            ],
            temperature=0.0,
            max_tokens=160,
            json_mode=True,
        )
        rewritten = (resp.json_data or {}).get("rewritten", "").strip()
        if rewritten:
            return rewritten
    except Exception:  # noqa: BLE001
        pass
    # Fallback: concatenate previous task + new refinement
    return f"{prev_user} ({state.rm_query})" if prev_user else state.rm_query


def _coerce_plan(raw: dict[str, Any]) -> Plan:
    steps: list[PlanStep] = []
    for s in raw.get("steps", []) or []:
        try:
            steps.append(PlanStep(**s))
        except Exception:  # noqa: BLE001
            continue
    return Plan(
        intent=raw.get("intent", "find_high_value_customers"),
        target_product=raw.get("target_product"),
        city_filter=raw.get("city_filter") or None,
        tone=raw.get("tone", "professional"),
        steps=steps,
    )


def _default_plan(target_product: str = "PROD-LOAN-PL") -> Plan:
    """Hard fallback so the agent always has a runnable plan."""
    return Plan(
        intent="find_high_value_customers_and_outreach",
        target_product=target_product,
        tone="professional",
        steps=[
            PlanStep(step=1, tool="query_customers",
                     args={"min_balance": 200000, "limit": 80, "exclude_products": [target_product]},
                     expected="Shortlist of customers."),
            PlanStep(step=2, tool="compute_customer_value",
                     args={"customer_ids": "$step1.ids"},
                     expected="Value score per customer."),
            PlanStep(step=3, tool="predict_loan_propensity",
                     args={"customer_ids": "$step1.ids", "product_id": target_product},
                     expected="Propensity per candidate."),
            PlanStep(step=4, tool="recommend_products",
                     args={"customer_ids": "$step3.top_k",
                           "candidate_product_ids": [target_product], "top_k": 1},
                     expected="Best-fit product per customer."),
            PlanStep(step=5, tool="search_interactions",
                     args={"query": "loan financing eligibility", "k": 5},
                     expected="RAG snippets for grounding."),
        ],
    )


async def run_planner(state: AgentState) -> AgentState:
    router = get_llm_router()
    sys_prompt = _load_system()

    # Follow-up: rewrite into a standalone task using history before planning.
    if state.intent == "follow_up" and state.history:
        rewritten = await _rewrite_follow_up(state)
        state.rewritten_query = rewritten
        state.emit(TraceEvent(event="info", data={"node": "follow_up", "rewritten": rewritten}))
        user_msg = rewritten.strip()
    else:
        user_msg = state.rm_query.strip()

    if not user_msg:
        state.plan = _default_plan()
        state.emit(TraceEvent(event="plan", data={"plan": state.plan.model_dump(), "source": "default"}))
        return state

    resp = await router.complete(
        kind="reasoning",
        messages=[
            LLMMessage(role="system", content=sys_prompt),
            LLMMessage(role="user", content=user_msg),
        ],
        temperature=0.2,
        max_tokens=900,
        json_mode=True,
    )
    raw = resp.json_data
    if not isinstance(raw, dict):
        logger.warning("Planner returned non-JSON; using default plan.")
        plan = _default_plan()
    else:
        plan = _coerce_plan(raw)
        if not plan.steps:
            plan = _default_plan(plan.target_product or "PROD-LOAN-PL")
    state.plan = plan
    state.emit(TraceEvent(
        event="plan",
        data={"plan": plan.model_dump(), "intent": plan.intent, "target_product": plan.target_product},
        llm_route=resp.meta.get("route_used", resp.provider),
        latency_ms=resp.latency_ms,
    ))
    return state
