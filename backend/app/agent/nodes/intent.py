"""Intent gate — runs before the Planner.

Not every message is a CRM task. Greetings, small talk, "what is this?", or
off-topic questions should get a short conversational reply, NOT a full
customer-hunt pipeline. This node classifies the message and, for non-task
input, produces a friendly response and signals the graph to stop early.
"""
from __future__ import annotations

import re

from app.agent.state import AgentState, TraceEvent
from app.infrastructure.llm import LLMMessage, get_llm_router

# Strong signals that the RM actually wants the CRM pipeline.
_TASK_PATTERNS = re.compile(
    r"\b(find|show|list|identify|customers?|loan|card|overdraft|sip|invest|"
    r"propensity|convert|conversion|outreach|whatsapp|message|campaign|"
    r"high[- ]?value|segment|cross[- ]?sell|upsell|retention|slowdown|"
    r"recommend|score|target|leads?|prospects?|portfolio|narrow|filter)\b",
    re.IGNORECASE,
)

_GREETING_PATTERNS = re.compile(
    r"^\s*(hi|hey|hello|yo|hola|namaste|good (morning|afternoon|evening)|"
    r"sup|what'?s up|how are you|thanks?|thank you|ok(ay)?|cool|nice|"
    r"who are you|what (is|are) (this|you)|help|\?+)\s*[!.?]*\s*$",
    re.IGNORECASE,
)

_HELP_TEXT = (
    "I'm RM Copilot — I help you find high-value customers, score their likelihood "
    "to convert, and draft compliant WhatsApp outreach.\n\n"
    "Try asking me something like:\n"
    "• \"Find high-value customers likely to convert for a personal loan this month "
    "and draft WhatsApp messages.\"\n"
    "• \"Show affluent customers in Bangalore for a premium credit card.\"\n"
    "• \"Which customers show salary-credit slowdown — what should we offer them?\"\n\n"
    "I'll show my reasoning step-by-step and list candidates on the right with an "
    "editable, compliance-checked draft for each."
)


def _looks_like_task(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # Very short messages that are pure greetings → not a task
    if _GREETING_PATTERNS.match(t):
        return False
    # Otherwise, require at least one CRM-task keyword
    return bool(_TASK_PATTERNS.search(t))


async def run_intent(state: AgentState) -> bool:
    """Return True if this is a CRM task (proceed to Planner), False if handled here."""
    text = state.rm_query or ""

    is_task = _looks_like_task(text)

    # If keyword heuristic is ambiguous (no greeting match, no task keyword),
    # ask a real LLM to classify — but only when one is configured (not mock),
    # so offline behaviour stays deterministic.
    router = get_llm_router()
    if not is_task and not _GREETING_PATTERNS.match(text.strip()) and router.status().get("gemini"):
        try:
            resp = await router.complete(
                kind="reasoning",
                messages=[
                    LLMMessage(role="system", content=(
                        "Classify the user's message for a banking RM assistant. "
                        "Reply with exactly one word: TASK if they want to find/score/"
                        "target customers or draft outreach; CHAT for greetings, "
                        "small talk, or general questions."
                    )),
                    LLMMessage(role="user", content=text),
                ],
                temperature=0.0,
                max_tokens=4,
            )
            is_task = resp.text.strip().upper().startswith("TASK")
        except Exception:  # noqa: BLE001
            pass

    state.emit(TraceEvent(
        event="info",
        data={"node": "intent", "classified": "task" if is_task else "chat"},
    ))

    if is_task:
        return True

    # Conversational reply — short-circuit the pipeline.
    state.final_summary = _conversational_reply(text)
    state.emit(TraceEvent(event="synth", data={"summary": state.final_summary, "candidate_count": 0, "mode": "chat"}))
    return False


def _conversational_reply(text: str) -> str:
    t = text.strip().lower()
    if re.match(r"^\s*(thanks?|thank you|ok(ay)?|cool|nice)\b", t):
        return "Anytime, Rohan. Whenever you're ready, tell me which segment or product to target and I'll pull the list."
    if "who are you" in t or "what is this" in t or "what are you" in t or "help" in t:
        return _HELP_TEXT
    # default greeting
    return f"Hi Rohan! {_HELP_TEXT}"
