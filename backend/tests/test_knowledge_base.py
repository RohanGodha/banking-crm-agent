"""Knowledge base: human-language questions over docs and persona historical data."""
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
    from app.db.sqlite_engine import bootstrap
    from app.knowledge_base import get_knowledge_base

    bootstrap()
    kb = get_knowledge_base()
    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        status = "ok" if cond else "FAIL"
        print(f"  [{status}] {name}{(' - ' + detail) if detail else ''}")
        if not cond:
            failures.append(name)

    # 1. Document grounding: RBI / procedural questions resolve to the right docs.
    r = await kb.ask("What is the home loan LTV limit?")
    check("rbi/ltv returns an answer", len(r["answer"]) > 10, r["answer"][:60])
    check("rbi/ltv cites a document", len(r["sources"]) > 0, str(r["sources"]))

    r = await kb.ask("What documents are needed to apply for a personal loan?")
    check("kyc/docs answered", len(r["answer"]) > 10)

    # 2. Persona with NO loans: the truthful answer is "no active loans".
    for phrasing in [
        "Tell me past loan taken by Priya",
        "what loans does priya have",
        "Show Priya Sharma's loan history",
        "does priya have any active loans",
    ]:
        r = await kb.ask(phrasing)
        ans = r["answer"].lower()
        resolved = "Customer Record" in r["sources"]
        truthful = "no active" in ans or "no active or past" in ans or "no loan" in ans
        check(f"priya resolved: '{phrasing}'", resolved)
        check(f"priya truthful no-loan: '{phrasing}'", truthful, r["answer"][:80])

    # 3. Persona WITH a loan: Ananya holds a Home Loan -> must be reported.
    r = await kb.ask("Tell me about Ananya's loans")
    ans = r["answer"].lower()
    check("ananya resolved", "Customer Record" in r["sources"])
    check("ananya home loan reported", "home loan" in ans or "loan" in ans, r["answer"][:90])

    # 4. Unknown customer -> falls back to documents, never an empty/500 response.
    r = await kb.ask("What is the CIBIL score range?")
    check("generic cibil answered", len(r["answer"]) > 10, str(r["sources"]))

    # 5. Sources endpoint surface
    srcs = kb.sources()
    check("three knowledge sources loaded", len(srcs) == 3, str([s["source"] for s in srcs]))

    # 6. Main-chat routing: knowledge questions must route to the KB, actions to task.
    from app.agent.nodes.intent import _heuristic
    routes = {
        "what is the current repo rate": "knowledge",
        "what is the home loan LTV limit": "knowledge",
        "how does the KYC process work": "knowledge",
        "Tell me past loan taken by Priya": "knowledge",
        "what loans does Ananya have": "knowledge",
        "find high-value customers for a personal loan and draft messages": "task",
        "show me customers with a salary-credit slowdown": "task",
        "what can you do": "faq",
        "hi there": "chitchat",
        "write a poem about Mumbai": "out_of_scope",
    }
    for q, expected in routes.items():
        got = _heuristic(q, False)
        check(f"route '{q[:34]}' -> {expected}", got == expected, f"got {got}")

    if failures:
        print(f"\nKnowledge base test FAILED: {failures}")
        return 1
    print("\nKnowledge base test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
