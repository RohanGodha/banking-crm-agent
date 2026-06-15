"""Critic node — checks the latest tool call and decides pass/fail/replan."""
from __future__ import annotations

from app.agent.state import AgentState, TraceEvent


async def run_critic(state: AgentState) -> AgentState:
    if not state.tool_calls:
        return state
    last = state.tool_calls[-1]

    verdict = "pass"
    replan = False
    notes = "Tool returned successfully."

    if not last.ok:
        verdict = "fail"
        replan = True
        notes = f"{last.tool} failed: {last.error}"
    elif isinstance(last.output, dict):
        # heuristic empty-result detection
        if last.tool == "query_customers" and len(last.output.get("customers", [])) == 0:
            verdict = "fail"
            replan = True
            notes = "No customers matched the filters; loosen criteria."
        elif last.tool == "predict_loan_propensity" and len(last.output.get("customers", [])) == 0:
            notes = "No propensity rows returned; proceed but expect empty candidate set."

    state.emit(TraceEvent(
        event="critic",
        data={"step": last.step, "tool": last.tool, "verdict": verdict, "replan": replan, "notes": notes},
    ))
    if verdict == "fail" and replan and state.replans < 1:
        state.replans += 1
        # naive recovery: relax filters and retry once
        if last.tool == "query_customers" and state.plan:
            step = state.plan.steps[state.cursor]
            step.args = {k: v for k, v in step.args.items() if k not in {"min_balance", "min_income", "cities"}}
            step.args["limit"] = 200
            step.done = False
            # Pop the failed record so it re-runs cleanly
            state.tool_calls.pop()
            state.emit(TraceEvent(event="info", data={"action": "replan", "tool": last.tool, "new_args": step.args}))
            return state
    state.cursor += 1
    return state
