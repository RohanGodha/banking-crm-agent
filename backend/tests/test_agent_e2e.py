"""Full agent run — Planner → Tools → Critic → Synthesizer → MessageGen → Responder."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def run() -> int:
    from app.agent import AgentState, run_agent
    from app.db.sqlite_engine import bootstrap

    bootstrap()
    state = AgentState(
        rm_query=(
            "Find high-value customers likely to convert for a personal loan this month "
            "and generate personalized WhatsApp messages."
        ),
    )
    print(f">>> Session id: {state.session_id}")
    event_counts: dict[str, int] = {}
    async for ev in run_agent(state):
        event_counts[ev.event] = event_counts.get(ev.event, 0) + 1
        if ev.event in ("plan", "tool_result", "critic", "synth", "final"):
            data_keys = list(ev.data.keys())[:6]
            print(f"  [{ev.event}] keys={data_keys}")
    print(f"\n>>> Event counts: {event_counts}")
    print(f">>> Plan steps: {len(state.plan.steps) if state.plan else 0}")
    print(f">>> Tool calls: {len(state.tool_calls)}")
    print(f">>> Candidates: {len(state.candidates)}")
    print(f">>> Drafts:     {len(state.drafts)}")
    print(f">>> Summary ({len(state.final_summary)} chars):")
    print("    " + state.final_summary[:240].replace("\n", " "))
    print(f"\n>>> Top 3 candidates:")
    for c in state.candidates[:3]:
        print(f"  - {c.name:25s} comp={c.composite_score:.2f}  v={c.value_score:.2f}  p={c.propensity_score:.2f}  -> {c.recommended_product_name}")
    print(f"\n>>> Sample draft (first):")
    if state.drafts:
        print(f"    {state.drafts[0].message[:280]}")
        print(f"    compliance.ok = {state.drafts[0].compliance.get('ok')}")

    assert state.plan is not None, "Plan was not produced"
    assert len(state.tool_calls) >= 4, f"Expected ≥4 tool calls, got {len(state.tool_calls)}"
    assert len(state.candidates) >= 1, "No candidates produced"
    assert len(state.drafts) >= 1, "No drafts produced"
    print("\nAgent E2E test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
