from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel

from app.application.tool_registry import tool
from app.infrastructure.datasource import get_datasource
from app.scoring.propensity import predict_propensity


class RecommendIn(BaseModel):
    customer_ids: list[str]
    candidate_product_ids: list[str] | None = None
    top_k: int = 1


class Recommendation(BaseModel):
    customer_id: str
    product_id: str
    product_name: str
    propensity_score: float
    eligible: bool
    reasons: list[str]


class RecommendOut(BaseModel):
    source: str
    recommendations: list[Recommendation]
    latency_ms: int


def _eligibility_ok(customer: dict[str, Any], product: dict[str, Any]) -> tuple[bool, list[str]]:
    elig: dict[str, Any] = product.get("eligibility") or {}
    reasons: list[str] = []
    age = int(customer.get("age") or 0)
    income = float(customer.get("monthly_income") or 0)

    if (min_age := elig.get("min_age")) is not None and age < min_age:
        reasons.append(f"age {age} below min_age {min_age}")
    if (max_age := elig.get("max_age")) is not None and age > max_age:
        reasons.append(f"age {age} above max_age {max_age}")
    if (min_inc := elig.get("min_income")) is not None and income < min_inc:
        reasons.append(f"income {income:.0f} below min_income {min_inc:.0f}")
    if elig.get("kyc") == "verified" and customer.get("kyc_status") != "verified":
        reasons.append("KYC not verified")
    if isinstance(elig.get("risk_appetite"), list):
        if customer.get("risk_appetite") not in elig["risk_appetite"]:
            reasons.append(f"risk_appetite {customer.get('risk_appetite')} not in {elig['risk_appetite']}")
    return (len(reasons) == 0), reasons


@tool(
    name="recommend_products",
    description=(
        "For each customer, recommend the best-fit product among an optional candidate list "
        "(defaults to the full catalog), ranking by propensity and filtering for eligibility."
    ),
    input_model=RecommendIn,
    output_model=RecommendOut,
)
async def recommend_products(args: RecommendIn) -> RecommendOut:
    started = time.perf_counter()
    ds = get_datasource()
    prod_res = await ds.get_products()
    products: list[dict[str, Any]] = prod_res.data or []
    if args.candidate_product_ids:
        products = [p for p in products if p["id"] in args.candidate_product_ids]
    # Exclude non-actionable categories
    products = [p for p in products if p["category"] in {"loan", "card", "investment", "overdraft"}]

    customers_map, txns_map, holdings_map, interactions_map = await asyncio.gather(
        ds.get_customers_bulk(args.customer_ids),
        ds.get_transactions_bulk(args.customer_ids, 6),
        ds.get_holdings_bulk(args.customer_ids),
        ds.get_interactions_bulk(args.customer_ids),
    )

    recs: list[Recommendation] = []
    for cid in args.customer_ids:
        cust = customers_map.get(cid)
        if not cust:
            continue
        hr = holdings_map.get(cid, [])
        tr = txns_map.get(cid, [])
        ir = interactions_map.get(cid, [])
        candidates: list[Recommendation] = []
        for prod in products:
            # Skip products the customer already holds (active)
            if any(h["product_id"] == prod["id"] for h in hr):
                continue
            score, _ = predict_propensity(cust, tr, hr, ir, prod["id"])
            eligible, reasons = _eligibility_ok(cust, prod)
            candidates.append(
                Recommendation(
                    customer_id=cid,
                    product_id=prod["id"],
                    product_name=prod["name"],
                    propensity_score=score,
                    eligible=eligible,
                    reasons=reasons or ["meets all eligibility rules"],
                )
            )
        _ = ir  # interactions reserved for future reason-codes
        candidates.sort(key=lambda r: (r.eligible, r.propensity_score), reverse=True)
        recs.extend(candidates[: args.top_k])

    return RecommendOut(
        source=prod_res.source,
        recommendations=recs,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
