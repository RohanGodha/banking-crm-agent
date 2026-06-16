"""Verify sentiment/escalation enrichment + multilingual draft routing."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def run() -> int:
    from app.db.sqlite_engine import bootstrap
    from app.infrastructure.datasource import get_datasource
    from app.scoring.sentiment import analyze_sentiment

    bootstrap()
    ds = get_datasource()

    # Ananya (HERO-003) has an "EMI stress" interaction → negative + escalate.
    ananya = await ds.get_interactions("CUST-HERO-003")
    s = analyze_sentiment(ananya.data or [])
    print(f"Ananya  -> sentiment={s['sentiment']} escalate={s['escalate']} churn={s['churn_risk']} signals={s['signals']}")
    assert s["sentiment"] == "negative", f"expected negative, got {s['sentiment']}"
    assert s["escalate"] is True

    # Priya (HERO-001) notes are positive/neutral → not escalated.
    priya = await ds.get_interactions("CUST-HERO-001")
    sp = analyze_sentiment(priya.data or [])
    print(f"Priya   -> sentiment={sp['sentiment']} escalate={sp['escalate']}")
    assert sp["escalate"] is False

    # Multilingual + sentiment through the full agent.
    from app.agent import AgentState, run_agent
    state = AgentState(rm_query="Find customers with salary slowdown for retention and draft messages in Hindi")
    async for _ in run_agent(state):
        pass
    print(f"\nPlan language: {state.plan.language}")
    assert state.plan.language == "Hindi"
    escalated = [c for c in state.candidates if c.escalate]
    print(f"Candidates: {len(state.candidates)}  escalated: {len(escalated)}")
    for c in state.candidates[:5]:
        print(f"  {c.name:20} sentiment={c.sentiment:8} escalate={c.escalate}")

    print("\nSentiment + multilingual test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
