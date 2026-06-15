from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from app.application.tool_registry import tool
from app.domain import ScoreBreakdown
from app.infrastructure.datasource import get_datasource
from app.scoring.value import compute_value


class ComputeValueIn(BaseModel):
    customer_ids: list[str]
    months: int = 6


class CustomerValue(BaseModel):
    customer_id: str
    value_score: float
    breakdown: list[ScoreBreakdown]


class ComputeValueOut(BaseModel):
    source: str
    customers: list[CustomerValue]
    latency_ms: int


@tool(
    name="compute_customer_value",
    description=(
        "Compute an explainable customer value score (0-1) per customer ID, based on balance, "
        "income, tenure and transaction velocity z-scored against the candidate population. "
        "Returns top contributing features."
    ),
    input_model=ComputeValueIn,
    output_model=ComputeValueOut,
)
async def compute_customer_value(args: ComputeValueIn) -> ComputeValueOut:
    import time
    started = time.perf_counter()
    ds = get_datasource()

    # Bulk-fetch profiles + transactions in 2 queries (instead of 2N).
    customers_map = await ds.get_customers_bulk(args.customer_ids)
    txns_map = await ds.get_transactions_bulk(args.customer_ids, args.months)

    population: list[dict[str, Any]] = []
    velocity_map: dict[str, int] = {}
    for cid, cust in customers_map.items():
        velocity_map[cid] = len(txns_map.get(cid, []))
        cust["_txn_velocity"] = velocity_map[cid]
        population.append(cust)

    out: list[CustomerValue] = []
    for cid, cust in customers_map.items():
        score, breakdown = compute_value(cust, population, txn_count_6m=velocity_map.get(cid, 0))
        out.append(CustomerValue(customer_id=cid, value_score=score, breakdown=breakdown))

    out.sort(key=lambda c: c.value_score, reverse=True)
    return ComputeValueOut(
        source=getattr(ds, "name", "sqlite"),
        customers=out,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
