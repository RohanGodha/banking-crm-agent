from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from app.application.tool_registry import tool
from app.infrastructure.datasource import get_datasource


class GetTransactionsIn(BaseModel):
    customer_id: str
    months: int = Field(default=6, ge=1, le=24)


class TxnAggregates(BaseModel):
    total_credit: float = 0.0
    total_debit: float = 0.0
    avg_monthly_credit: float = 0.0
    avg_monthly_debit: float = 0.0
    txn_count: int = 0
    by_category: dict[str, float] = {}
    largest_debit: float = 0.0
    largest_debit_category: str | None = None


class GetTransactionsOut(BaseModel):
    source: str
    customer_id: str
    months: int
    aggregates: TxnAggregates
    transactions: list[dict[str, Any]]
    latency_ms: int


@tool(
    name="get_transactions",
    description=(
        "Return recent transactions for a customer along with aggregates: total credit/debit, "
        "monthly averages, category split, and the largest debit. Used as input to scoring."
    ),
    input_model=GetTransactionsIn,
    output_model=GetTransactionsOut,
)
async def get_transactions(args: GetTransactionsIn) -> GetTransactionsOut:
    ds = get_datasource()
    res = await ds.get_transactions(args.customer_id, args.months)
    txns: list[dict[str, Any]] = res.data or []

    cat_totals: dict[str, float] = defaultdict(float)
    total_credit = 0.0
    total_debit = 0.0
    largest_debit_amt = 0.0
    largest_debit_cat: str | None = None
    for t in txns:
        amt = float(t["amount"])
        cat = t.get("category") or "other"
        cat_totals[cat] += amt
        if amt > 0:
            total_credit += amt
        else:
            total_debit += -amt
            if -amt > largest_debit_amt:
                largest_debit_amt = -amt
                largest_debit_cat = cat

    agg = TxnAggregates(
        total_credit=round(total_credit, 2),
        total_debit=round(total_debit, 2),
        avg_monthly_credit=round(total_credit / args.months, 2),
        avg_monthly_debit=round(total_debit / args.months, 2),
        txn_count=len(txns),
        by_category={k: round(v, 2) for k, v in cat_totals.items()},
        largest_debit=round(largest_debit_amt, 2),
        largest_debit_category=largest_debit_cat,
    )
    return GetTransactionsOut(
        source=res.source,
        customer_id=args.customer_id,
        months=args.months,
        aggregates=agg,
        transactions=txns,
        latency_ms=res.latency_ms,
    )
