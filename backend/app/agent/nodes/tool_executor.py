"""Tool executor — resolves placeholders, dispatches, records the result."""
from __future__ import annotations

from typing import Any

from app.agent.state import AgentState, ToolCallRecord, TraceEvent
from app.application.tool_registry import invoke_tool


def _resolve_placeholders(state: AgentState, args: dict[str, Any]) -> dict[str, Any]:
    """Replace `$stepN.ids` / `$stepN.top_k` references with real values."""
    resolved: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str) and value.startswith("$step"):
            resolved[key] = _resolve_one(state, value)
        elif isinstance(value, list):
            resolved[key] = [
                (_resolve_one(state, v) if isinstance(v, str) and v.startswith("$step") else v)
                for v in value
            ]
        else:
            resolved[key] = value
    return resolved


def _resolve_one(state: AgentState, ref: str) -> Any:
    """ref like '$step1.ids' or '$step2.top_k' """
    try:
        body = ref[5:]  # strip "$step"
        n_str, _, attr = body.partition(".")
        n = int(n_str)
    except ValueError:
        return ref
    tc = next((t for t in state.tool_calls if t.step == n and t.ok), None)
    if tc is None:
        return []
    out = tc.output or {}
    if attr == "ids":
        if tc.tool == "query_customers":
            return [c["id"] for c in out.get("customers", [])]
        if tc.tool == "compute_customer_value":
            return [c["customer_id"] for c in out.get("customers", [])]
    if attr == "top_k":
        # Pass a *wide* shortlist into the next scoring stage so the final
        # composite ranking (value + propensity) is meaningful. If we capped at
        # 10 here, a high-propensity / moderate-value customer (e.g. a retention
        # target with a stress signal) would be filtered out before propensity
        # is ever computed. The synthesizer trims to the real top-K afterwards.
        k = 40
        if tc.tool == "compute_customer_value":
            return [c["customer_id"] for c in out.get("customers", [])[:k]]
        if tc.tool == "predict_loan_propensity":
            return [c["customer_id"] for c in out.get("customers", [])[:k]]
    return out


async def execute_step(state: AgentState, step_index: int) -> AgentState:
    if not state.plan or step_index >= len(state.plan.steps):
        return state
    step = state.plan.steps[step_index]
    args = _resolve_placeholders(state, step.args)
    state.emit(TraceEvent(event="tool_call", data={"step": step.step, "tool": step.tool, "args": args}))

    envelope = await invoke_tool(step.tool, args)
    record = ToolCallRecord(
        step=step.step,
        tool=step.tool,
        args=args,
        ok=envelope["ok"],
        source=(envelope.get("data") or {}).get("source") if envelope["ok"] else None,
        latency_ms=envelope["latency_ms"],
        output=envelope.get("data"),
        error=envelope.get("error"),
    )
    state.tool_calls.append(record)
    step.done = record.ok

    # Build a compact result payload for SSE
    summary: dict[str, Any] = {
        "step": step.step,
        "tool": step.tool,
        "ok": record.ok,
        "source": record.source,
        "latency_ms": record.latency_ms,
    }
    if record.ok and isinstance(record.output, dict):
        if "customers" in record.output and isinstance(record.output["customers"], list):
            summary["rows"] = len(record.output["customers"])
        elif "recommendations" in record.output:
            summary["rows"] = len(record.output["recommendations"])
        elif "matches" in record.output:
            summary["rows"] = len(record.output["matches"])
    if not record.ok:
        summary["error"] = record.error

    state.emit(TraceEvent(
        event="tool_result",
        data=summary,
        latency_ms=record.latency_ms,
    ))
    return state
