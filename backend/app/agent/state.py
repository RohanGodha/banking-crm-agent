"""Agent state — pure Pydantic, JSON-serialisable, stored verbatim in `agent_traces`."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step: int
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    expected: str = ""
    done: bool = False


class Plan(BaseModel):
    intent: str = ""
    target_product: str | None = None
    city_filter: list[str] | None = None
    tone: str = "professional"
    language: str = "English"          # target language for outreach drafts
    steps: list[PlanStep] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    step: int
    tool: str
    args: dict[str, Any]
    ok: bool
    source: str | None = None
    latency_ms: int = 0
    output: Any = None
    error: str | None = None


class TraceEvent(BaseModel):
    """One event in the agent's reasoning timeline. SSE-friendly."""
    event: Literal[
        "plan", "router", "tool_call", "tool_result", "critic", "synth",
        "candidate", "draft", "token", "final", "error", "info",
    ]
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    data: dict[str, Any] = Field(default_factory=dict)
    llm_route: str | None = None
    latency_ms: int | None = None


class CandidateRecord(BaseModel):
    customer_id: str
    name: str
    city: str
    segment: str
    monthly_income: float | None = None
    avg_balance_6m: float | None = None
    value_score: float
    propensity_score: float
    composite_score: float
    recommended_product_id: str
    recommended_product_name: str
    top_features: list[dict[str, Any]]
    rationale: str
    citations: list[str] = Field(default_factory=list)
    # Sentiment / churn-risk from interaction notes
    sentiment: str = "neutral"          # positive | neutral | negative
    escalate: bool = False              # flag for priority human attention
    churn_risk: bool = False


class DraftRecord(BaseModel):
    customer_id: str
    product_id: str
    message: str
    compliance: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rm_query: str = ""
    rm_name: str = "Rohan"

    # Conversation memory: prior turns [{role, content}] loaded from the session.
    history: list[dict[str, str]] = Field(default_factory=list)
    intent: str = "task"          # task | follow_up | faq | chitchat | out_of_scope
    rewritten_query: str | None = None  # set when a follow_up is expanded

    plan: Plan | None = None
    cursor: int = 0
    iterations: int = 0
    replans: int = 0

    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    candidates: list[CandidateRecord] = Field(default_factory=list)
    drafts: list[DraftRecord] = Field(default_factory=list)

    final_summary: str = ""
    error: str | None = None
    events: list[TraceEvent] = Field(default_factory=list)
    # `archive` accumulates every event for the whole run and is never drained,
    # so the Responder can persist the complete trace even though `events` is
    # drained incrementally for SSE streaming.
    archive: list[TraceEvent] = Field(default_factory=list)

    def emit(self, ev: TraceEvent) -> None:
        self.events.append(ev)
        self.archive.append(ev)

    def scratchpad(self) -> dict[str, Any]:
        """Lightweight view of recent tool outputs the LLM can consume."""
        return {
            "rm_query": self.rm_query,
            "plan": self.plan.model_dump() if self.plan else None,
            "completed_steps": [
                {"step": tc.step, "tool": tc.tool, "ok": tc.ok, "source": tc.source}
                for tc in self.tool_calls
            ],
            "candidate_count": len(self.candidates),
        }
