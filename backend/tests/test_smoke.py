"""End-to-end smoke test of the SQLite + tools + scoring layers."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow `python tests\test_smoke.py` style direct runs
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.application.tool_registry import get_registry, invoke_tool
    from app.db.sqlite_engine import bootstrap

    print(">>> Bootstrapping SQLite + seeding…")
    bootstrap()

    print(">>> Registering tools…")
    reg = get_registry()
    expected = {
        "query_customers", "get_transactions", "compute_customer_value",
        "predict_loan_propensity", "recommend_products", "search_interactions",
        "generate_whatsapp_message", "create_outreach_batch",
    }
    missing = expected - set(reg.keys())
    assert not missing, f"missing tools: {missing}"
    print(f"    OK — {len(reg)} tools registered: {sorted(reg.keys())}")

    print(">>> query_customers (HNW Mumbai)…")
    res = asyncio.run(invoke_tool("query_customers", {"cities": ["Mumbai"], "segments": ["hnw"], "limit": 10}))
    assert res["ok"], res
    data = res["data"]
    print(f"    OK — source={data['source']}, rows={data['rows']}")
    assert data["rows"] >= 1, "Expected Priya at minimum"
    assert any(c["id"] == "CUST-HERO-001" for c in data["customers"]), "Priya not in results"
    print(f"    Priya found at position "
          f"{[c['id'] for c in data['customers']].index('CUST-HERO-001') + 1}")

    print(">>> compute_customer_value on first 20 customers…")
    ids = [c["id"] for c in data["customers"]] + ["CUST-HERO-002", "CUST-HERO-003", "CUST-HERO-004", "CUST-HERO-005"]
    res = asyncio.run(invoke_tool("compute_customer_value", {"customer_ids": ids[:20]}))
    assert res["ok"], res
    print("    OK — top 3 value scores: " +
          ", ".join(f"{c['customer_id']}={c['value_score']:.2f}" for c in res['data']['customers'][:3]))

    print(">>> predict_loan_propensity (PROD-LOAN-PL)…")
    res = asyncio.run(invoke_tool("predict_loan_propensity", {
        "customer_ids": ["CUST-HERO-001", "CUST-HERO-002", "CUST-HERO-003"],
        "product_id": "PROD-LOAN-PL",
    }))
    assert res["ok"], res
    scores = {c["customer_id"]: c["propensity_score"] for c in res["data"]["customers"]}
    print(f"    OK — scores: {scores}")
    assert scores["CUST-HERO-001"] >= 0.5, f"Priya propensity should be ≥0.5: {scores['CUST-HERO-001']}"

    print(">>> recommend_products for Vikram (expecting credit card)…")
    res = asyncio.run(invoke_tool("recommend_products", {
        "customer_ids": ["CUST-HERO-004"], "top_k": 2,
    }))
    assert res["ok"], res
    recs = res["data"]["recommendations"]
    print("    OK — top recs: " +
          ", ".join(f"{r['product_id']} ({r['propensity_score']:.2f})" for r in recs))

    print(">>> generate_whatsapp_message for Priya (mock LLM)…")
    res = asyncio.run(invoke_tool("generate_whatsapp_message", {
        "customer_id": "CUST-HERO-001",
        "product_id": "PROD-LOAN-PL",
        "tone": "professional",
        "top_features": [],
        "rm_name": "Rohan",
    }))
    assert res["ok"], res
    print(f"    OK — message ({len(res['data']['message'])} chars): "
          f"{res['data']['message'][:120]}…")
    print(f"    compliance.ok = {res['data']['compliance']['ok']}")

    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
