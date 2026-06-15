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
    filters = CustomerFilters(**args.model_dump())
    res = await ds.find_customers(filters)
    return QueryCustomersOut(
        source=res.source,
        rows=res.rows,
        customers=res.data or [],
        latency_ms=res.latency_ms,
    )
