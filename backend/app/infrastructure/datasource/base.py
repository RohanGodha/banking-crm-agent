"""DataSource port (Protocol). Hexagonal architecture.

All tools depend on this Protocol, never on a concrete adapter.
The FailoverSource composes SQLite + Databricks behind the same contract,
so swapping the warehouse is one line of code.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.domain import Customer, CustomerFilters, Product, Transaction


class DataSourceResult(BaseModel):
    """Wraps every DataSource call so the trace can record provenance."""
    source: str = Field(description="databricks | sqlite | sqlite(failover)")
    latency_ms: int = 0
    rows: int = 0
    data: Any = None


@runtime_checkable
class DataSource(Protocol):
    name: str

    async def find_customers(self, filters: CustomerFilters) -> DataSourceResult: ...
    async def get_customer(self, customer_id: str) -> DataSourceResult: ...
    async def get_transactions(
        self, customer_id: str, months: int = 6
    ) -> DataSourceResult: ...
    async def get_products(self) -> DataSourceResult: ...
    async def get_holdings(self, customer_id: str) -> DataSourceResult: ...
    async def get_interactions(self, customer_id: str | None = None) -> DataSourceResult: ...
    async def health(self) -> bool: ...


# Convenience aliases the rest of the code uses

CustomersResult = DataSourceResult
CustomerResult = DataSourceResult
TransactionsResult = DataSourceResult


__all__ = [
    "DataSource",
    "DataSourceResult",
    "Customer",
    "CustomerFilters",
    "Product",
    "Transaction",
]
