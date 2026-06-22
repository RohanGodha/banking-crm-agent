"""Intent gate — classifies the RM's message into a route before any work.

Routes: task | follow_up | faq | chitchat | out_of_scope

Strategy: a fast heuristic first pass, upgraded by an LLM classifier
(INTENT_PROMPT) whenever a real provider is configured. Conversation history is
considered so refinements are recognised as follow_ups.
"""
from __future__ import annotations

import re

from app.agent.prompts import CHITCHAT_PROMPT, GUARDRAIL_PROMPT, INTENT_PROMPT, SYSTEM_PROMPT
from app.agent.state import AgentState, TraceEvent
from app.infrastructure.llm import LLMMessage, get_llm_router

_TASK_PATTERNS = re.compile(
    r"\b(find|show|list|identify|pull|get|customers?|loan|card|overdraft|sip|invest|"
    r"propensity|convert|conversion|outreach|whatsapp|message|campaign|"
    r"high[- ]?value|segment|cross[- ]?sell|upsell|retention|slowdown|"
    r"recommend|score|target|leads?|prospects?|portfolio)\b",
    re.IGNORECASE,
)
_FOLLOWUP_PATTERNS = re.compile(
    r"^\s*(now|also|instead|just|only|then|and|but|make (it|them)|narrow|"
    r"filter|exclude|include|top \d+|change|warmer|formal|shorter|longer|"
    r"more|less|same but)\b",
    re.IGNORECASE,
)
_GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hey|hello|yo|hola|namaste|good (morning|afternoon|evening)|"
    r"sup|what'?s up|how are you|thanks?|thank you|ok(ay)?|cool|nice|bye|goodbye)"
    r"(\s+(there|team|copilot|rm|rohan|buddy|mate|all))?\s*[!.?]*\s*$",
    re.IGNORECASE,
)
_FAQ_PATTERNS = re.compile(
    r"(who are you|what (is|are|can) (this|you)|what do you do|how do you|"
    r"what data|which products?|can you|do you (send|support)|help\b|capabilit)",
    re.IGNORECASE,
)
_OUT_OF_SCOPE = re.compile(
    r"\b(weather|poem|joke|code|python|football|cricket score|movie|recipe|"
    r"translate|stock price|news)\b",
    re.IGNORECASE,
)
# Action verbs that mean "run the customer pipeline" — these win over knowledge.
_ACTION_PATTERNS = re.compile(
    r"\b(find|identify|pull|segment|shortlist|target|draft|generate|score|"
    r"recommend|outreach|campaign|cross[- ]?sell|upsell|prospect)\b",
    re.IGNORECASE,
)
# Informational banking questions answerable from the reference knowledge base.
_KNOWLEDGE_PATTERNS = re.compile(
    r"\b(rbi|repo rate|reverse repo|crr|slr|bank rate|interest rate|cibil|credit score|"
    r"kyc|ckyc|v-?cip|ltv|foir|dti|emi|foreclos|prepay|dicgc|priority sector|"
    r"section 80c|section 24|key facts|kfs|eligibilit|moratorium|penal|"
    r"how (do|to|does) .*(apply|kyc|loan)|documents? (needed|required)|process of)\b",
    re.IGNORECASE,
)
_PERSONA_HISTORY = re.compile(
    r"\b(past|previous|existing|active|current)\s+loans?\b"
    r"|\bloans?\s+(taken|history|held|by|of|for|does)\b"
    r"|\bwhat\s+loans?\b"
    r"|'s\s+(loan|loans|credit|holdings?|products?|account|cibil|salary|history|transactions?)\b"
    r"|\b(loan|credit|repayment|holdings?|products?|account|cibil|salary|transaction)s?\s+(history|record|details?)\b",
    re.IGNORECASE,
)

VALID_INTENTS = {"task", "follow_up", "knowledge", "faq", "chitchat", "out_of_scope"}


def _is_question_about_assistant(t: str) -> bool:
    """'what can you do', 'which products can you recommend' → FAQ, not a task."""
    if not _FAQ_PATTERNS.search(t):
        return False
    # Phrased as a question to the assistant (mentions you/your or ends with ?)
    return bool(re.search(r"\b(you|your)\b", t, re.IGNORECASE) or t.strip().endswith("?"))


def _heuristic(text: str, has_history: bool) -> str:
    t = (text or "").strip()
    if not t:
        return "chitchat"
    if _GREETING_PATTERNS.match(t):
        return "chitchat"
    if _OUT_OF_SCOPE.search(t):
        return "out_of_scope"
    # Questions ABOUT the assistant's capabilities are FAQ, even if they contain
    # task-like words ("what products can you recommend?").
    if _is_question_about_assistant(t):
        return "faq"
    if has_history and _FOLLOWUP_PATTERNS.match(t) and not _TASK_PATTERNS.search(t):
        return "follow_up"
    # Action verbs mean "run the pipeline" → task wins over knowledge.
    if _ACTION_PATTERNS.search(t):
        return "task"
    # Informational banking questions / a named customer's history → knowledge base.
    if _KNOWLEDGE_PATTERNS.search(t) or _PERSONA_HISTORY.search(t):
        return "knowledge"
    if _TASK_PATTERNS.search(t):
        if has_history and _FOLLOWUP_PATTERNS.match(t):
            return "follow_up"
        return "task"
    if _FAQ_PATTERNS.search(t):
        return "faq"
    return "faq"  # default: treat unknown as a question, not a customer hunt


async def classify_intent(state: AgentState) -> str:
    text = state.rm_query or ""
    has_history = len(state.history) > 0
    intent = _heuristic(text, has_history)

    router = get_llm_router()
    # Upgrade with LLM classifier when a real provider exists.
    if router.status().get("gemini") or router.status().get("groq"):
        try:
            convo = "\n".join(f"{h['role']}: {h['content']}" for h in state.history[-4:])
            resp = await router.complete(
                kind="reasoning",
                messages=[
                    LLMMessage(role="system", content=INTENT_PROMPT),
                    LLMMessage(role="user", content=f"Recent conversation:\n{convo or '(none)'}\n\nNew message: {text}"),
                ],
                temperature=0.0,
                max_tokens=40,
                json_mode=True,
            )
            data = resp.json_data or {}
            cand = str(data.get("intent", "")).strip().lower()
            if cand in VALID_INTENTS:
                intent = cand
        except Exception:  # noqa: BLE001
            pass

    state.intent = intent
    state.emit(TraceEvent(event="info", data={"node": "intent", "intent": intent, "has_history": has_history}))
    return intent


async def run_chitchat(state: AgentState) -> AgentState:
    name = state.rm_name or "Rohan"
    router = get_llm_router()
    try:
        convo = "\n".join(f"{h['role']}: {h['content']}" for h in state.history[-4:])
        resp = await router.complete(
            kind="reasoning",
            messages=[
                LLMMessage(role="system", content=f"{SYSTEM_PROMPT}\n\n{CHITCHAT_PROMPT}"),
                LLMMessage(role="user", content=(
                    f"RM name: {name}\n"
                    f"Recent conversation:\n{convo or '(none)'}\n\n"
                    f"RM just said: {state.rm_query}"
                )),
            ],
            temperature=0.7,
            max_tokens=120,
        )
        text = resp.text.strip()
        route = resp.meta.get("route_used", resp.provider)
    except Exception:  # noqa: BLE001
        text = (
            f"Hi {name}! I'm RM Copilot. Tell me which customers to target and I'll find them, "
            "score their likelihood to convert, recommend a product, and draft WhatsApp outreach."
        )
        route = None

    state.final_summary = text
    state.emit(TraceEvent(
        event="synth",
        data={"summary": text, "candidate_count": 0, "mode": "chitchat"},
        llm_route=route,
    ))
    return state


async def run_guardrail(state: AgentState) -> AgentState:
    router = get_llm_router()
    try:
        resp = await router.complete(
            kind="reasoning",
            messages=[
                LLMMessage(role="system", content=SYSTEM_PROMPT + "\n\n" + GUARDRAIL_PROMPT),
                LLMMessage(role="user", content=state.rm_query),
            ],
            temperature=0.3,
            max_tokens=120,
        )
        text = resp.text.strip()
    except Exception:  # noqa: BLE001
        text = (
            "That's outside what I can help with. I'm your banking CRM copilot — I can find "
            "customers, score conversion likelihood, recommend products, and draft outreach."
        )
    state.final_summary = text
    state.emit(TraceEvent(event="synth", data={"summary": text, "candidate_count": 0, "mode": "out_of_scope"}))
    return state
