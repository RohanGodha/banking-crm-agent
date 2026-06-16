from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.application.tool_registry import tool
from app.domain import CustomerFilters
from app.infrastructure.datasource import get_datasource


class QueryCustomersIn(BaseModel):
    cities: list[str] | None = Field(default=None, description="City filter, e.g. ['Mumbai'].")
    segments: list[str] | None = Field(default=None, description="['mass','mass_affluent','affluent','hnw'].")
    min_income: float | None = None
    max_income: float | None = None
    min_balance: float | None = None
    min_age: int | None = None
    max_age: int | None = None
    risk_appetite: list[str] | None = None
    exclude_products: list[str] | None = Field(
        default=None,
        description="Skip customers who already hold any of these product IDs.",
    )
    limit: int = 200


class QueryCustomersOut(BaseModel):
    source: str
    rows: int
    customers: list[dict[str, Any]]
    latency_ms: int


@tool(
    name="query_customers",
    description=(
        "Search the customer base with structured filters (city, segment, income, balance, age, "
        "risk appetite). Returns enriched customer rows including balance and avg_balance_6m."
    ),
    input_model=QueryCustomersIn,
    output_model=QueryCustomersOut,
)
async def query_customers(args: QueryCustomersIn) -> QueryCustomersOut:
    ds = get_datasource()
    raw = args.model_dump()
    # The LLM often emits 0 instead of null for unset min/max thresholds,
    # and 0 values for age/balance/income filters are meaningless (they
    # would produce WHERE age <= 0, killing all results). Treat them as None.
    for key in ("min_income", "max_income", "min_balance", "min_age", "max_age"):
        if key in raw and raw[key] == 0:
            raw[key] = None
    filters = CustomerFilters(**raw)
    res = await ds.find_customers(filters)
    return QueryCustomersOut(
        source=res.source,
        rows=res.rows,
        customers=res.data or [],
        latency_ms=res.latency_ms,
    )
