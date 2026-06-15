from __future__ import annotations

import asyncio
import time

from pydantic import BaseModel

from app.application.tool_registry import tool
from app.domain import ScoreBreakdown
from app.infrastructure.datasource import get_datasource
from app.scoring.propensity import predict_propensity


class PredictPropensityIn(BaseModel):
    customer_ids: list[str]
    product_id: str


class CustomerPropensity(BaseModel):
    customer_id: str
    product_id: str
    propensity_score: float
    breakdown: list[ScoreBreakdown]


class PredictPropensityOut(BaseModel):
    source: str
    product_id: str
    customers: list[CustomerPropensity]
    latency_ms: int


@tool(
    name="predict_loan_propensity",
    description=(
        "Predict the propensity (0-1) of each customer to convert for a specific product. "
        "Weighted logistic over product-specific behavioural signals; returns top driving "
        "features for explainability."
    ),
    input_model=PredictPropensityIn,
    output_model=PredictPropensityOut,
)
async def predict_loan_propensity(args: PredictPropensityIn) -> PredictPropensityOut:
    started = time.perf_counter()
    ds = get_datasource()

    # Bulk-fetch everything in 4 queries (instead of 4N).
    customers_map, txns_map, holdings_map, interactions_map = await asyncio.gather(
        ds.get_customers_bulk(args.customer_ids),
        ds.get_transactions_bulk(args.customer_ids, 6),
        ds.get_holdings_bulk(args.customer_ids),
        ds.get_interactions_bulk(args.customer_ids),
    )

    out: list[CustomerPropensity] = []
    for cid in args.customer_ids:
        cust = customers_map.get(cid)
        if not cust:
            continue
        score, breakdown = predict_propensity(
            customer=cust,
            txns=txns_map.get(cid, []),
            holdings=holdings_map.get(cid, []),
            interactions=interactions_map.get(cid, []),
            product_id=args.product_id,
        )
        out.append(
            CustomerPropensity(
                customer_id=cid,
                product_id=args.product_id,
                propensity_score=score,
                breakdown=breakdown,
            )
        )

    out.sort(key=lambda c: c.propensity_score, reverse=True)
    return PredictPropensityOut(
        source=getattr(ds, "name", "sqlite"),
        product_id=args.product_id,
        customers=out,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
